from waldo_common.db.session import session_scope
from tests.classes import CDCTestCase

import time
import unittest
import json


class TestNotifications(CDCTestCase):
    def test_startup_with_existing_unprocessed_events(self):
        """
        Test plan:
            1) start with service not running (down)
            2) insert some albums (an instrumented table)
            3) launch cdc service
            4) expect events get processed in order without errors
        """
        self.ensure_service_is_down()

        sorted_album_uuids = []  # sorted by insertion order (asc)
        for i in range(20):
            with session_scope() as session:
                a_rv = self.df.create_album()
                sorted_album_uuids.append(a_rv['uuid'])

        with session_scope() as session:
            result = session.execute("""
            select * from cdc_events
            where table_name = 'albums'
              and row_data_updates->>'uuid' in :sorted_album_uuids
            """, dict(sorted_album_uuids=tuple(sorted_album_uuids))).fetchall()

            unprocessed_event_rows = {row['id']: dict(row) for row in result}

        sorted_event_ids = sorted(list(unprocessed_event_rows.keys()))
        print("sorted_album_uuids", sorted_album_uuids)
        print("sorted_event_ids", sorted_event_ids)
        for a_uuid, event_id in zip(sorted_album_uuids, sorted_event_ids):
            self.assertEqual(unprocessed_event_rows[event_id]['row_data_updates']['uuid'], a_uuid)

        # launch service and check for processed cdc events
        self.ensure_service_is_up()

        found_them = False
        for i in range(30):
            with session_scope() as session:
                result = session.execute("""
                select * from cdc_events
                where id = :event_id
                  and is_processed = true
                """, dict(event_id=sorted_event_ids[-1])).fetchone()
            if result is None:
                print("waiting on cdc events to process")
                time.sleep(1)
            else:
                found_them = True
                with session_scope() as session:
                    result = session.execute("""
                    select * from cdc_events
                    where id in :event_ids
                    """, dict(event_ids=tuple(sorted_event_ids))).fetchall()

                    processed_event_rows = {row['id']: dict(row) for row in result}

                last_seen_updated_at = processed_event_rows[sorted_event_ids[0]]['updated_at']
                for event_id in sorted_event_ids[1:]:
                    self.assertTrue(processed_event_rows[event_id]['updated_at'] >= last_seen_updated_at)
                    self.assertTrue(processed_event_rows[event_id]['error_message'] is None)

        self.assertTrue(found_them)
        self.assert_num_error_messages(0)

    def test_processing_via_notifications(self):
        """
        Test plan:
            1) start with service running (up)
            2) insert some albums (an instrumented table)
            3) expect events get processed in order without errors
        """
        sorted_album_uuids = []  # sorted by insertion order (asc)
        for i in range(20):
            with session_scope() as session:
                a_rv = self.df.create_album()
                sorted_album_uuids.append(a_rv['uuid'])

        with session_scope() as session:
            result = session.execute("""
            select * from cdc_events
            where table_name = 'albums'
              and row_data_updates->>'uuid' in :sorted_album_uuids
            """, dict(sorted_album_uuids=tuple(sorted_album_uuids))).fetchall()

            unprocessed_event_rows = {row['id']: dict(row) for row in result}

        sorted_event_ids = sorted(list(unprocessed_event_rows.keys()))
        print("sorted_album_uuids", sorted_album_uuids)
        print("sorted_event_ids", sorted_event_ids)
        for a_uuid, event_id in zip(sorted_album_uuids, sorted_event_ids):
            self.assertEqual(unprocessed_event_rows[event_id]['row_data_updates']['uuid'], a_uuid)

        found_them = False
        for i in range(30):
            with session_scope() as session:
                result = session.execute("""
                select * from cdc_events
                where id = :event_id
                  and is_processed = true
                """, dict(event_id=sorted_event_ids[-1])).fetchone()
            if result is None:
                print("waiting on cdc events to process")
                time.sleep(1)
            else:
                found_them = True
                with session_scope() as session:
                    result = session.execute("""
                    select * from cdc_events
                    where id in :event_ids
                    """, dict(event_ids=tuple(sorted_event_ids))).fetchall()

                    processed_event_rows = {row['id']: dict(row) for row in result}

                last_seen_updated_at = processed_event_rows[sorted_event_ids[0]]['updated_at']
                for event_id in sorted_event_ids[1:]:
                    self.assertTrue(processed_event_rows[event_id]['updated_at'] >= last_seen_updated_at)
                    self.assertTrue(processed_event_rows[event_id]['error_message'] is None)

        self.assertTrue(found_them)
        self.assert_num_error_messages(0)

    def test_error_in_handler(self):
        """
        Test plan:
            1) start with service running (up)
            2) manually write to cdc_cvents for faux table '__crash_test__'
            3) expect events get processed in with errors persisted
        """
        with session_scope() as session:
            row_data_updates = json.dumps({'some_fake_row': 'some_fake_data'})
            event_id = session.execute("""
            INSERT INTO cdc_events (table_name, operation_name, row_data_updates, created_at)
            VALUES ('__crash_test__', 'INSERT', :row_data_updates, now())
            RETURNING id
            """, dict(row_data_updates=row_data_updates)).fetchone()[0]

        found_them = False
        for i in range(30):
            with session_scope() as session:
                result = session.execute("""
                SELECT * FROM cdc_events
                WHERE id = :event_id
                  AND is_processed = true
                """, dict(event_id=event_id)).fetchone()
            if result is None:
                print("waiting on cdc event to process")
                time.sleep(1)
            else:
                found_them = True
                error_message = result.error_message
                print(error_message)
                self.assertTrue(error_message is not None)

        self.assertTrue(found_them)
        error_message = self.get_error_messages(1)[0]
        self.assertTrue(error_message['parameters']['event_id'], event_id)

    def test_disconnections_from_pg(self):
        """
        Test plan:
            1) start with service and postgres running
            2) insert some albums (an instrumented table)
            3) use postgres to disconnect the service's notification listener
            4) insert some more albums
            5) expect all events get processed in order without errors
        """
        sorted_album_uuids = []  # sorted by insertion order (asc)
        for i in range(100):
            if i % 25 == 0:
                self.disconnect_cdc_service_notification_listener()

            with session_scope() as session:
                a_rv = self.df.create_album()
                sorted_album_uuids.append(a_rv['uuid'])
            time.sleep(0.01)

        found_them = False
        for i in range(30):
            with session_scope() as session:
                result = session.execute("""
                select * from cdc_events
                where table_name = 'albums'
                  and is_processed = true
                  and row_data_updates->>'uuid' in :sorted_album_uuids
                """, dict(sorted_album_uuids=tuple(sorted_album_uuids))).fetchall()
            if len(result) != len(sorted_album_uuids):
                print("waiting on cdc events to process")
                time.sleep(1)
            else:
                found_them = True
                processed_event_rows = {row['id']: dict(row) for row in result}

                last_seen_updated_at = min([row['updated_at'] for row in processed_event_rows.values()])
                for event_id in sorted(processed_event_rows.keys())[1:]:
                    self.assertTrue(processed_event_rows[event_id]['updated_at'] >= last_seen_updated_at)
                    self.assertTrue(processed_event_rows[event_id]['error_message'] is None)

        self.assertTrue(found_them)
        self.assert_num_error_messages(0)
