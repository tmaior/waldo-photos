from waldo_cdc.settings import settings
from waldo_common.amqp.client import AMQPClient
from waldo_common.db.data_fabricator import DataFabricator
from waldo_common.db.session import session_scope
from waldo_common.test_helpers import got_target_count, RMQTestCase
from waldo_common.logging_utils import setup_logging
from contextlib import contextmanager

import time

TIMEOUT = 60

setup_logging()

client = AMQPClient()

@contextmanager
def wait_for_cdc(test_case):
    with session_scope() as session:
        def check_for_cdc_finished():
            STATEMENT = '''
            SELECT *
            FROM cdc_events
            ORDER BY id desc
            LIMIT 1
            '''
            result = session.execute(STATEMENT).fetchone()
            if result is None:
                return 1
            else:
                if result.is_processed:
                    return 1
                else:
                    return 0

        got_target_count(count_producer=check_for_cdc_finished, target=1,
                interval=0.2, timeout=60, settling_periods=1)
        test_case.empty_queues()
        yield session

    with session_scope() as session:
        def check_for_cdc_finished():
            STATEMENT = '''
            SELECT *
            FROM cdc_events
            ORDER BY id desc
            LIMIT 1
            '''
            result = session.execute(STATEMENT).fetchone()
            if result is None:
                return 1
            else:
                if result.is_processed:
                    return 1
                else:
                    return 0
        got_target_count(count_producer=check_for_cdc_finished, target=1,
                interval=0.2, timeout=60, settling_periods=1)
    time.sleep(0.5)


class CDCTestCase(RMQTestCase):
    def setUp(self, default_settling_periods=1, default_timeout=0.0, default_interval=1):
        self.client = AMQPClient()
        self.df = DataFabricator()
        self.ensure_service_is_up()
        self.wait_for_declarations(self.empty_queues)
        self.default_settling_periods = default_settling_periods
        self.default_timeout = default_timeout
        self.default_interval = default_interval

    def wait_for_declarations(self, fn):
        for i in range(3):
            try:
                return fn()
            except Exception as e:
                print("Waiting for Queues to be declared: %s" % str(e))
                time.sleep(1)

    def empty_queues(self):
        print("Emptying queues")
        t_start = time.time()
        for queue_name in (settings.error_routing_key,
                           settings.photo_prep_routing_key,
                           settings.slack_routing_key,
                           settings.hive_next_routing_key,
                           settings.comms_routing_key,
                           settings.time_matcher_routing_key,
                           settings.reference_face_coordinator_routing_key,
                           settings.health_check_routing_key,
                           settings.state_routing_key,
                           settings.matched_photo_aggregator_routing_key,
                           settings.notifications_routing_key,
                           settings.photo_share_blocker_routing_key,
                           settings.photo_router_routing_key,
                           settings.face_matcher_routing_key):
            self.client.get_messages(queue_name=queue_name)
        self.client.get_messages(queue_name=settings.face_surveyor_routing_key,
                max_priority=settings.max_priority)
        t_end = time.time()
        print("Emptied queues: took %s seconds" % (t_end - t_start))

    def get_error_messages(self, num):
        self.assert_num_error_messages(num)
        return self.client.get_messages(queue_name=settings.error_routing_key)

    def assert_num_error_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_error_messages, target=num, **kwargs))

    def get_num_error_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.error_routing_key, **kwargs)

    def get_photo_prep_messages(self, num):
        self.assert_num_photo_prep_messages(num)
        return self.client.get_messages(queue_name=settings.photo_prep_routing_key)

    def assert_num_photo_prep_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_photo_prep_messages, target=num, **kwargs))

    def get_num_photo_prep_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.photo_prep_routing_key, **kwargs)

    def get_slack_messages(self, num):
        self.assert_num_slack_messages(num)
        return self.client.get_messages(queue_name=settings.slack_routing_key)

    def assert_num_slack_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_slack_messages, target=num, **kwargs))

    def get_num_slack_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.slack_routing_key, **kwargs)

    def get_hive_next_messages(self, num):
        self.assert_num_hive_next_messages(num)
        return self.client.get_messages(queue_name=settings.hive_next_routing_key)

    def assert_num_hive_next_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_hive_next_messages, target=num, **kwargs))

    def get_num_hive_next_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.hive_next_routing_key, **kwargs)

    def get_comms_messages(self, num):
        self.assert_num_comms_messages(num)
        return self.client.get_messages(queue_name=settings.comms_routing_key)

    def assert_num_comms_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_comms_messages, target=num, **kwargs))

    def get_num_comms_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.comms_routing_key, **kwargs)

    def get_time_matcher_messages(self, num):
        self.assert_num_time_matcher_messages(num)
        return self.client.get_messages(queue_name=settings.time_matcher_routing_key)

    def assert_num_time_matcher_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_time_matcher_messages, target=num, **kwargs))

    def get_num_time_matcher_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.time_matcher_routing_key, **kwargs)

    def get_reference_face_coordinator_messages(self, num):
        self.assert_num_reference_face_coordinator_messages(num)
        return self.client.get_messages(queue_name=settings.reference_face_coordinator_routing_key)

    def assert_num_reference_face_coordinator_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_reference_face_coordinator_messages, target=num, **kwargs))

    def get_num_reference_face_coordinator_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.reference_face_coordinator_routing_key, **kwargs)

    def get_health_check_messages(self, num):
        self.assert_num_health_check_messages(num)
        return self.client.get_messages(queue_name=settings.health_check_routing_key)

    def assert_num_health_check_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_health_check_messages, target=num, **kwargs))

    def get_num_health_check_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.health_check_routing_key, **kwargs)

    def get_state_messages(self, num):
        self.assert_num_state_messages(num)
        return self.client.get_messages(queue_name=settings.state_routing_key)

    def assert_num_state_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_state_messages, target=num, **kwargs))

    def get_num_state_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.state_routing_key, **kwargs)

    def get_notifications_messages(self, num):
        self.assert_num_notifications_messages(num)
        return self.client.get_messages(queue_name=settings.notifications_routing_key)

    def assert_num_notifications_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_notifications_messages, target=num, **kwargs))

    def get_num_notifications_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.notifications_routing_key, **kwargs)

    def get_matched_photo_aggregator_messages(self, num):
        self.assert_num_matched_photo_aggregator_messages(num)
        return self.client.get_messages(queue_name=settings.matched_photo_aggregator_routing_key)

    def assert_num_matched_photo_aggregator_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_matched_photo_aggregator_messages, target=num, **kwargs))

    def get_num_matched_photo_aggregator_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.matched_photo_aggregator_routing_key, **kwargs)

    def get_photo_share_blocker_messages(self, num):
        self.assert_num_photo_share_blocker_messages(num)
        return self.client.get_messages(queue_name=settings.photo_share_blocker_routing_key)

    def assert_num_photo_share_blocker_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_photo_share_blocker_messages, target=num, **kwargs))

    def get_num_photo_share_blocker_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.photo_share_blocker_routing_key, **kwargs)

    def get_photo_router_messages(self, num):
        self.assert_num_photo_router_messages(num)
        return self.client.get_messages(queue_name=settings.photo_router_routing_key)

    def assert_num_photo_router_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_photo_router_messages, target=num, **kwargs))

    def get_num_photo_router_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.photo_router_routing_key, **kwargs)

    def get_face_matcher_messages(self, num):
        self.assert_num_face_matcher_messages(num)
        return self.client.get_messages(queue_name=settings.face_matcher_routing_key)

    def assert_num_face_matcher_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_face_matcher_messages, target=num, **kwargs))

    def get_num_face_matcher_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.face_matcher_routing_key, **kwargs)

    def get_face_surveyor_messages(self, num):
        self.assert_num_face_surveyor_messages(num)
        return self.client.get_messages(queue_name=settings.face_surveyor_routing_key,
                max_priority=settings.max_priority)

    def assert_num_face_surveyor_messages(self, num=0, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval,
                'settling_periods': self.default_settling_periods, **kwargs}
        self.assertTrue(got_target_count(count_producer=self.get_num_face_surveyor_messages, target=num, **kwargs))

    def get_num_face_surveyor_messages(self, **kwargs):
        kwargs = {'timeout': self.default_timeout, 'interval':self.default_interval, **kwargs}
        return self.client.get_message_count(settings.face_surveyor_routing_key, **kwargs)

    def service_is_listening(self):
        with session_scope() as session:
            STATEMENT = "select * from pg_stat_activity where query like 'LISTEN%'"
            listening = session.execute(STATEMENT).fetchone() is not None
        if listening:
            print("Service is listening")
        else:
            print("Service is not listening")
        return listening

    def disconnect_cdc_service_notification_listener(self):
        with session_scope() as session:
            session.execute("""
            select pg_terminate_backend(pid)
            from pg_stat_activity where
            query like 'LISTEN%'
            """)

    def ensure_service_is_up(self, max_attempts=int(TIMEOUT), period=1):
        print("Ensuring service is listening")
        if self.service_is_listening():
            return
        else:
            with open('/repo/.command_pipe', 'w') as cfile:
                cfile.write("docker-compose up -d cdc_service &>> test_logs/up_cdc_service.log\n")

            num_attempts = 0
            while True:
                num_attempts += 1
                if self.service_is_listening() or num_attempts > max_attempts:
                    break
                else:
                    print("Waiting on cdc service to be listening for cdc_events inserts")
                    time.sleep(period)

    def ensure_service_is_down(self, max_attempts=int(TIMEOUT), period=1):
        print("Ensuring service is not listening")
        if not self.service_is_listening():
            return
        else:
            with open('/repo/.command_pipe', 'w') as cfile:
                cfile.write("docker-compose stop cdc_service\n")
                cfile.write("docker logs cdc_service &>> test_logs/service.log\n")

            num_attempts = 0
            while True:
                num_attempts += 1
                if (not self.service_is_listening()) or num_attempts > max_attempts:
                    break
                else:
                    print("Waiting on cdc service to no longer be listening for cdc_events inserts")
                    time.sleep(period)
