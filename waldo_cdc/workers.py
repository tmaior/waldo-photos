from amqp import exceptions
from structlog import get_logger
from waldo_cdc import handlers
from waldo_cdc.cdc_event import CDCEvent
from waldo_cdc.http.blueprint import construct_blueprint
from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient
from waldo_common.amqp.utils import declare_queue, declare_queue_without_dead_letter_queue
from waldo_common.db.session import session_scope
from waldo_common.http.webapp import Webapp
from waldo_common.process_management.healthcheck import HealthCheckWorker
from waldo_common.process_management.worker import Worker
from waldo_common.settings.db import settings as db_settings

import asyncio
import asyncpg
import json
import os
import time
import traceback
import pprint


LOG = get_logger()


class HTTPWorker(HealthCheckWorker):
    NAME = 'http'

    def start(self):
        with session_scope() as session:
            engine = session.bind
            engine.dispose()

        webapp = Webapp(blueprint=construct_blueprint(self.is_healthy))
        webapp.start()


class NotificationWorker(Worker):
    NAME = 'notification'

    def start(self):
        with session_scope() as session:
            engine = session.bind
            engine.dispose()

        declare_queue(settings.comms_routing_key)
        declare_queue(settings.error_routing_key)
        declare_queue(settings.face_matcher_routing_key)
        declare_queue(settings.face_surveyor_routing_key, max_priority=settings.max_priority)
        declare_queue(settings.hive_next_routing_key)
        declare_queue(settings.matched_photo_aggregator_routing_key)
        declare_queue(settings.notifications_routing_key)
        declare_queue(settings.reference_face_coordinator_routing_key)
        declare_queue(settings.time_matcher_routing_key)
        declare_queue_without_dead_letter_queue(settings.health_check_routing_key)

        try:
            declare_queue(settings.photo_share_blocker_routing_key)
        except exceptions.PreconditionFailed:
            # this queue exists without dead-letter-exchanges configured
            pass

        try:
            declare_queue(settings.slack_routing_key)
        except exceptions.PreconditionFailed:
            # this queue exists without dead-letter-exchanges configured
            pass

        try:
            declare_queue(settings.photo_prep_routing_key)
        except exceptions.PreconditionFailed:
            # this queue may exist with different queue max-priority setting
            pass


        registered_handlers = {
            'album_album_folder_tags': handlers.AlbumAlbumFolderTagsHandler(),
            'album_folder_shares': handlers.AlbumFolderSharesHandler(),
            'album_folders_members': handlers.AlbumFoldersMembersHandler(),
            'albums': handlers.AlbumsHandler(),
            'album_shares': handlers.AlbumSharesHandler(),
            'albums_memberships': handlers.AlbumsMembershipsHandler(),
            'auth_phone_verifications': handlers.AuthPhoneVerificationsHandler(),
            'face_match_votes': handlers.FaceMatchVotesHandler(),
            'health_check': handlers.HealthCheckHandler(),
            'identity_uniform_album_folder_tags': handlers.IdentityUniformAlbumFolderTagsHandler(),
            'matched_photo_deliveries': handlers.MatchedPhotoDeliveriesHandler(),
            'matched_photos': handlers.MatchedPhotosHandler(),
            'photo_share_blocks': handlers.PhotoShareBlocksHandler(),
            'photostreams_photos': handlers.PhotostreamsPhotosHandler(),
            'pub_commandering_identities': handlers.PubCommanderingIdentitiesHandler(),
            'purchased_album_folders_identities': handlers.PurchasedAlbumFoldersIdentitiesHandler(),
            'purchased_albums_identities': handlers.PurchasedAlbumsIdentitiesHandler(),
            'roster_identity_linked_identities': handlers.RosterIdentityLinkedIdentitiesHandler(),
            'selected_identities': handlers.SelectedIdentitiesHandler(),
            'selected_identity_links': handlers.SelectedIdentityLinksHandler(),
            'subscribed_album_folders_identities': handlers.SubscribedAlbumFoldersIdentitiesHandler(),
            'transaction_refunds': handlers.TransactionRefundsHandler(),
            'uniform_album_folder_tags': handlers.UniformAlbumFolderTagsHandler(),
            'watermark_config': handlers.WatermarkConfigHandler(),
            'purchased_photos': handlers.PurchasedPhotosHandler(),
            'accounts': handlers.AccountsHandler(),


            '__crash_test__': handlers.CrashingHandler(),
        }

        # These offsets reduce the priority of the processing of these events
        # so that other events can get through faster.
        priority_offsets = {
            'face_match_votes': 1_000_000,
            'photostreams_photos': 2_000_000,
        }

        pending_cdc_events = asyncio.PriorityQueue()

        async def setup_listener(event_loop):
            conn = await asyncpg.connect(db_settings.db_connection_url, loop=event_loop)

            def term_listener(*args, **kwargs):
                LOG.critical("Postgres connection for notification listener lost... exiting")
                os._exit(2)
            conn.add_termination_listener(term_listener)

            STATEMENT = """
            SELECT * from pg_stat_activity where query like 'LISTEN "new_cdc_event"'
            """
            row = await conn.fetchrow(STATEMENT)
            if row is not None:
                LOG.critical("Someone is already listening for new_cdc_events... exiting",
                        db_row=pprint.pformat(dict(row)))
                os._exit(2)

            def listener(connection, pid, notification_name, notification_content):
                event_data = json.loads(notification_content)
                LOG.debug("received CDC event notification", event_id=event_data['id'],
                        table_name=event_data['table_name'], operation_name=event_data['operation_name'])
                priority_offset = priority_offsets.get(event_data['table_name'], 0)
                pending_cdc_events.put_nowait((event_data['id'] + priority_offset + 0.1, event_data))
            await conn.add_listener('new_cdc_event', listener)
            LOG.info("Listening for new_cdc_event notifications from postgres")

        async def backfill_queue_and_start_handling(event_loop):
            # backfill requires planning new database table and structure
            # 1) identify pending cdc events that need to be processed
            # 2) add them to our priority queue that's being added to by the notification listener
            # 3) begin handling pending_cdc_events, skipping duplicates

            conn = await asyncpg.connect(db_settings.db_connection_url, loop=event_loop)

            def term_listener(*args, **kwargs):
                LOG.critical("Postgres connection for event management was lost... exiting")
                os._exit(2)
            conn.add_termination_listener(term_listener)

            STATEMENT = """
            SELECT id, table_name, operation_name
            FROM cdc_events
            WHERE is_processed = false
            """
            results = await conn.fetch(STATEMENT)
            for row in results:
                LOG.debug("Fetched pending CDC event at startup", event_id=row['id'],
                        table_name=row['table_name'], operation_name=row['operation_name'])
                priority_offset = priority_offsets.get(row['table_name'], 0)
                pending_cdc_events.put_nowait((row['id'] + priority_offset, dict(row)))
            else:
                LOG.info("No pending CDC events at startup")

            last_processed_id = -1
            while True:
                _, pending_cdc_event = await pending_cdc_events.get()
                event_id = pending_cdc_event['id']
                if event_id == last_processed_id:
                    LOG.debug("Skipping duplicate CDC event", event_id=event_id)
                    continue
                else:
                    last_processed_id = event_id
                    FETCH_STATEMENT = 'SELECT * FROM cdc_events WHERE id = $1'
                    row = await conn.fetchrow(FETCH_STATEMENT, event_id)
                    cdc_event = CDCEvent.from_row(row)

                    begin_time = time.time()
                    LOG.debug("Handling CDC event", event_id=event_id)
                    handler = registered_handlers.get(cdc_event.table_name, None)
                    if handler is None:
                        cdc_event.error_message = f"No handler registered for table_name ({cdc_event.table_name})"
                    else:
                        try:
                            handler.handle_event(cdc_event)
                        except Exception as handler_exception:
                            LOG.exception("Handler Encountered Exception", **cdc_event.to_dict_for_logging())
                            error_message = traceback.format_exc()
                            cdc_event.error_message = error_message
                            try:
                                client = AMQPClient()
                                client.send(routing_key=settings.error_routing_key,
                                        endpoint='handler_error',
                                        parameters=cdc_event.to_dict_for_logging())
                            except:
                                pass
                    end_time = time.time()

                    UPDATE_STATEMENT, args = cdc_event.get_update_statement_and_args()
                    update_row = await conn.fetchrow(UPDATE_STATEMENT, *args)

                    if update_row is None:
                        LOG.error("Unable to update cdc_events", **cdc_event.to_dict_for_logging())
                    else:
                        cdc_event.is_processed = True
                        handler_took_ms = round((end_time - begin_time) * 1000.0, 3)
                        LOG.debug('metric', metric_data=dict(key='cdc.%s' % cdc_event.table_name,
                                                             kind='faster_is_better_timing',
                                                             took_ms=handler_took_ms,
                                                             description='CDC handler timing'))
                        LOG.debug("Completed processing CDC event", handler_took_ms=handler_took_ms,
                                **cdc_event.to_dict_for_logging())

        event_loop = asyncio.get_event_loop()
        event_loop.run_until_complete(setup_listener(event_loop))
        event_loop.run_until_complete(backfill_queue_and_start_handling(event_loop))
