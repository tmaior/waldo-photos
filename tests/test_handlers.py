from tests.classes import CDCTestCase, wait_for_cdc
from waldo_cdc.settings import settings
from waldo_common.db.session import session_scope
from waldo_common.test_helpers import got_target_count

import uuid


class TestAlbumFolderSharesHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            afs_rv = self.df.create_album_folder_share(session=session)
        print(afs_rv)

        self.assert_rmq_messages(f'''
        error: 0
        notifications:
          - endpoint: {settings.album_folder_share_created_endpoint}
            parameters:
              uuid: {afs_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE album_folder_shares SET updated_at = now()
            WHERE uuid = :afs_uuid
            """, dict(afs_uuid=afs_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next:
          - endpoint: {settings.album_folder_share_updated_endpoint}
            parameters:
              payload:
                uuid: {afs_rv['uuid']}
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE from album_folder_shares
            WHERE uuid = :afs_uuid
            """, dict(afs_uuid=afs_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        notifications: 0
        ''')


class TestAlbumFolderMembersHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            afm_rv = self.df.create_album_folders_member__album(session=session)
        print(afm_rv)

        self.assert_rmq_messages(f'''
        error: 0
        hive_next:
          - endpoint: {settings.album_folder_member_created_endpoint}
            parameters:
              payload:
                uuid: {afm_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE album_folders_members SET updated_at = now()
            WHERE uuid = :afm_uuid
            """, dict(afm_uuid=afm_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE from album_folders_members
            WHERE uuid = :afm_uuid
            """, dict(afm_uuid=afm_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        ''')


class TestAlbumsHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            a_rv = self.df.create_album(watermark_config_id=str(uuid.uuid4()),
                    session=session)
        print(a_rv)

        self.assert_rmq_messages(f'''
        error: 0
        photo_prep:
          - endpoint: {settings.album_updated_endpoint}
            parameters:
              uuid: {a_rv['uuid']}
        slack:
          - endpoint: {settings.album_created_endpoint}
            parameters:
              payload:
                id: {a_rv['id']}
                uuid: {a_rv['uuid']}
        matched_photo_aggregator: 0
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE albums SET watermark_config_id = :wc_uuid
            WHERE id = :album_id
            """, dict(wc_uuid=str(uuid.uuid4()), album_id=a_rv['id']))

        self.assert_rmq_messages(f'''
        error: 0
        photo_prep:
          - endpoint: {settings.album_updated_endpoint}
            parameters:
              uuid: {a_rv['uuid']}
        slack: 0
        matched_photo_aggregator: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE from albums
            WHERE id = :album_id
            """, dict(album_id=a_rv['id']))

        self.assert_rmq_messages(f'''
        error: 0
        photo_prep: 0
        matched_photo_aggregator: 0
        slack: 0
        ''')

    def test_insert_update_without_watermark_config(self):
        with wait_for_cdc(self) as session:
            a_rv = self.df.create_album(session=session)
        print(a_rv)

        self.assert_rmq_messages(f'''
        error: 0
        photo_prep:
          - endpoint: {settings.album_updated_endpoint}
            parameters:
              uuid: {a_rv['uuid']}
        slack:
          - endpoint: {settings.album_created_endpoint}
            parameters:
              payload:
                id: {a_rv['id']}
                uuid: {a_rv['uuid']}
        matched_photo_aggregator: 0
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE albums SET updated_at = now()
            WHERE id = :album_id
            """, dict(album_id=a_rv['id']))

        self.assert_rmq_messages(f'''
        error: 0
        photo_prep: 0
        slack: 0
        matched_photo_aggregator: 0
        ''')

    def test_soft_delete(self):
        with wait_for_cdc(self) as session:
            si_rv = self.df.create_selected_identity(session=session)
        print(si_rv)
        am_rv = si_rv['albums_membership_rv']
        a_rv = am_rv['album_rv']

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE albums SET soft_deleted = true
            WHERE id = :album_id
            """, dict(album_id=a_rv['id']))

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator:
          # albums soft deleted
          - endpoint: {settings.album_updated_endpoint}
            parameters:
              album_uuid: {a_rv['uuid']}
              soft_deleted: {True}
          # side effect because memberships were also soft-deleted
          - endpoint: {settings.album_membership_updated_endpoint}
            parameters:
              album_membership_uuid: {am_rv['uuid']}
              soft_deleted: {True}
        photo_prep: 0
        slack: 0
        ''')

        with session_scope() as session:
            def get_num_soft_deleted_am():
                result = session.execute("""
                SELECT * FROM albums_memberships
                WHERE album_id = :album_id
                  AND soft_deleted = true
                """, dict(album_id=a_rv['id'])).fetchall()
                return len([r for r in result])

            self.assertTrue(got_target_count(count_producer=get_num_soft_deleted_am, target=1))

    def test_update_type(self):
        with wait_for_cdc(self) as session:
            si_rv = self.df.create_selected_identity(session=session)
        print(si_rv)
        am_rv = si_rv['albums_membership_rv']
        a_rv = am_rv['album_rv']

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE albums SET album_type = 'shutterbug'
            WHERE id = :album_id
            """, dict(album_id=a_rv['id']))

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator:
          - endpoint: {settings.album_updated_endpoint}
            parameters:
              album_uuid: {a_rv['uuid']}
        photo_prep: 0
        slack: 0
        ''')

    def test_update_time_based_matching_enabled(self):
        with wait_for_cdc(self) as session:
            si_rv = self.df.create_selected_identity(session=session)
        print(si_rv)
        am_rv = si_rv['albums_membership_rv']
        a_rv = am_rv['album_rv']

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE albums SET time_based_matching_enabled = true
            WHERE id = :album_id
            """, dict(album_id=a_rv['id']))

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator: 0
        photo_router:
          - endpoint: {settings.time_based_matching_enabled_endpoint}
            parameters:
              album_uuid: {a_rv['uuid']}
        photo_prep: 0
        slack: 0
        ''')

    def test_update_subtype(self):
        with wait_for_cdc(self) as session:
            si_rv = self.df.create_selected_identity(session=session)
        print(si_rv)
        am_rv = si_rv['albums_membership_rv']
        a_rv = am_rv['album_rv']

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE albums SET album_subtype = 'events'
            WHERE id = :album_id
            """, dict(album_id=a_rv['id']))

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator:
          - endpoint: {settings.album_updated_endpoint}
            parameters:
              album_uuid: {a_rv['uuid']}
        photo_prep: 0
        slack: 0
        ''')

class TestAlbumSharesHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            as_rv = self.df.create_album_share(session=session)
        print(as_rv)

        self.assert_rmq_messages(f'''
        error: 0
        notifications:
          - endpoint: {settings.album_share_updated_endpoint}
            parameters:
              uuid: {as_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE album_shares SET updated_at = now()
            WHERE uuid = :as_uuid
            """, dict(as_uuid=as_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        notifications:
          - endpoint: {settings.album_share_updated_endpoint}
            parameters:
              uuid: {as_rv['uuid']}
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE from album_shares
            WHERE uuid = :as_uuid
            """, dict(as_uuid=as_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        notifications:
          - endpoint: {settings.album_share_updated_endpoint}
            parameters:
              uuid: {as_rv['uuid']}
        ''')


class TestAlbumsMembershipsHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            am_rv = self.df.create_albums_membership(session=session,
                                                     album_kwargs={'album_type': 'shutterbug'})
        print(am_rv)

        self.assert_rmq_messages(f'''
        error: 0
        notifications:
          - endpoint: {settings.album_membership_status_endpoint}
            parameters:
              uuid: {am_rv['uuid']}
              album_id: {am_rv['album_rv']['uuid']}
              receiver_account_id: {am_rv['receiver_account_rv']['uuid']}
        matched_photo_aggregator:
          - endpoint: {settings.album_membership_created_endpoint}
            parameters:
              album_id: {am_rv['album_rv']['id']}
              receiver_account_id: {am_rv['receiver_account_rv']['id']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE albums_memberships SET updated_at = now()
            WHERE album_id = :album_id
              AND receiver_account_id = :receiver_account_id
            """, dict(album_id=am_rv['album_rv']['id'], receiver_account_id=am_rv['receiver_account_rv']['id']))

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator: 0
        notifications:
          - endpoint: {settings.album_membership_status_endpoint}
            parameters:
              uuid: {am_rv['uuid']}
              album_id: {am_rv['album_rv']['uuid']}
              receiver_account_id: {am_rv['receiver_account_rv']['uuid']}
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE from albums_memberships
            WHERE album_id = :album_id
              AND receiver_account_id = :receiver_account_id
            """, dict(album_id=am_rv['album_rv']['id'], receiver_account_id=am_rv['receiver_account_rv']['id']))

        self.assert_rmq_messages(f'''
        error: 0
        notifications: 0
        matched_photo_aggregator: 0
        ''')

    def test_soft_deleted(self):
        with wait_for_cdc(self) as session:
            am_rv = self.df.create_albums_membership(session=session,
                                                     album_kwargs={'album_type': 'shutterbug'})

        # test an UPDATE - soft_deleted = true
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE albums_memberships SET soft_deleted = true
            WHERE album_id = :album_id
              AND receiver_account_id = :receiver_account_id
            """, dict(album_id=am_rv['album_rv']['id'], receiver_account_id=am_rv['receiver_account_rv']['id']))

        self.assert_rmq_messages(f'''
        error: 0
        notifications: 1
        matched_photo_aggregator:
          - endpoint: {settings.album_membership_updated_endpoint}
            parameters:
              album_membership_uuid: {am_rv['uuid']}
              soft_deleted: {True}
        ''')

class TestAuthPhoneVerificationsHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            apv_rv = self.df.create_auth_phone_verification(session=session)
        print(apv_rv)

        self.assert_rmq_messages(f'''
        error: 0
        slack:
          - endpoint: {settings.auth_phone_verification_created_endpoint}
            parameters:
              payload:
                uuid: {apv_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE auth_phone_verifications SET updated_at = now()
            WHERE uuid = :apv_uuid
            """, dict(apv_uuid=apv_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        slack: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE from auth_phone_verifications
            WHERE uuid = :apv_uuid
            """, dict(apv_uuid=apv_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        slack: 0
        ''')


class TestFaceMatchVotesHandler(CDCTestCase):
    def test_insert_update_delete(self):
        first_fmv_rv = self.df.create_face_match_vote()
        new_si_rv = self.df.create_selected_identity()

        with wait_for_cdc(self) as session:
            fmv_rv = self.df.create_face_match_vote(selected_identity_rv=new_si_rv,
                    selfie_face_rv=first_fmv_rv['selfie_face_rv'],
                    compared_face_rv=first_fmv_rv['compared_face_rv'],
                    vote='positive',
                    applied=True,
                    session=session)
        print(fmv_rv)

        self.assert_rmq_messages(f'''
        error: 0
        time_matcher:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              uuid: {fmv_rv['uuid']}
        reference_face_coordinator:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              uuid: {fmv_rv['uuid']}
        slack:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              payload:
                uuid: {fmv_rv['uuid']}
        face_matcher:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
                uuid: {fmv_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE face_match_votes SET updated_at = now()
            WHERE uuid = :fmv_uuid
            """, dict(fmv_uuid=fmv_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        time_matcher:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              uuid: {fmv_rv['uuid']}
        reference_face_coordinator:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              uuid: {fmv_rv['uuid']}
        slack:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              payload:
                uuid: {fmv_rv['uuid']}
        face_matcher:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
                uuid: {fmv_rv['uuid']}
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE from face_match_votes
            WHERE uuid = :fmv_uuid
            """, dict(fmv_uuid=fmv_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        time_matcher:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              uuid: {fmv_rv['uuid']}
        reference_face_coordinator:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              uuid: {fmv_rv['uuid']}
        slack:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              payload:
                uuid: {fmv_rv['uuid']}
        face_matcher:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
                uuid: {fmv_rv['uuid']}
        ''')

    def test_insert_update__not_positive(self):
        first_fmv_rv = self.df.create_face_match_vote()
        new_si_rv = self.df.create_selected_identity()

        with wait_for_cdc(self) as session:
            fmv_rv = self.df.create_face_match_vote(selected_identity_rv=new_si_rv,
                    selfie_face_rv=first_fmv_rv['selfie_face_rv'],
                    compared_face_rv=first_fmv_rv['compared_face_rv'],
                    vote='negative',
                    applied=True,
                    session=session)
        print(fmv_rv)

        self.assert_rmq_messages(f'''
        error: 0
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE face_match_votes SET updated_at = now()
            WHERE uuid = :fmv_uuid
            """, dict(fmv_uuid=fmv_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        ''')

    def test_insert_update__below_threshold(self):
        first_fmv_rv = self.df.create_face_match_vote()
        new_si_rv = self.df.create_selected_identity()

        with wait_for_cdc(self) as session:
            fmv_rv = self.df.create_face_match_vote(selected_identity_rv=new_si_rv,
                    selfie_face_rv=first_fmv_rv['selfie_face_rv'],
                    compared_face_rv=first_fmv_rv['compared_face_rv'],
                    vote='positive',
                    applied=True,
                    session=session)
        print(fmv_rv)

        self.assert_rmq_messages(f'''
        error: 0
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE face_match_votes SET updated_at = now()
            WHERE uuid = :fmv_uuid
            """, dict(fmv_uuid=fmv_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        ''')

    def test_update_cluster_uuid__skips_out(self):
        first_fmv_rv = self.df.create_face_match_vote()
        new_si_rv = self.df.create_selected_identity()

        with wait_for_cdc(self) as session:
            fmv_rv = self.df.create_face_match_vote(selected_identity_rv=new_si_rv,
                    selfie_face_rv=first_fmv_rv['selfie_face_rv'],
                    compared_face_rv=first_fmv_rv['compared_face_rv'],
                    vote='positive',
                    applied=True,
                    session=session)
        print(fmv_rv)

        self.assert_rmq_messages(f'''
        error: 0
        time_matcher:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              uuid: {fmv_rv['uuid']}
        reference_face_coordinator:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              uuid: {fmv_rv['uuid']}
        slack:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              payload:
                uuid: {fmv_rv['uuid']}
        face_matcher:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
                uuid: {fmv_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE face_match_votes SET cluster_uuid = :cluster_uuid
            WHERE uuid = :fmv_uuid
            """, dict(cluster_uuid=str(uuid.uuid4()), fmv_uuid=fmv_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        time_matcher: 0
        reference_face_coordinator: 0
        slack:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              payload:
                uuid: {fmv_rv['uuid']}
        face_matcher: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE from face_match_votes
            WHERE uuid = :fmv_uuid
            """, dict(fmv_uuid=fmv_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        time_matcher:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              uuid: {fmv_rv['uuid']}
        reference_face_coordinator:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              uuid: {fmv_rv['uuid']}
        slack:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
              payload:
                uuid: {fmv_rv['uuid']}
        face_matcher:
          - endpoint: {settings.face_match_vote_updated_endpoint}
            parameters:
                uuid: {fmv_rv['uuid']}
        ''')


class TestHealthCheckHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            result = session.execute("""
            INSERT INTO health_check
            DEFAULT VALUES
            RETURNING uuid""")
            hc_uuid = result.fetchone()['uuid']
        print(hc_uuid)

        self.assert_num_error_messages(0)
        hc_message = self.get_health_check_messages(1)[0]
        self.assertEqual(hc_message, {'status': 'OK'})

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE health_check SET updated_at = now()
            WHERE uuid = :hc_uuid
            """, dict(hc_uuid=hc_uuid))

        self.assert_num_error_messages(0)
        hc_message = self.get_health_check_messages(1)[0]
        self.assertEqual(hc_message, {'status': 'OK'})

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM health_check
            WHERE uuid = :hc_uuid
            """, dict(hc_uuid=hc_uuid))

        self.assert_num_error_messages(0)
        hc_message = self.get_health_check_messages(1)[0]
        self.assertEqual(hc_message, {'status': 'OK'})


class TestIdentityUniformAlbumFolderTagsHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            iuaft_rv = self.df.create_identity_uniform_album_folder_tag(jersey_number='42',
                    session=session)
        print(iuaft_rv)

        self.assert_rmq_messages(f'''
        error: 0
        state:
          - endpoint: {settings.jersey_number_updated_endpoint}
            parameters:
              uniform_album_folder_tag_level_uuid: {iuaft_rv['uniform_album_folder_tag_level_uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE identity_uniform_album_folder_tags SET updated_at = now()
            WHERE identity_album_folder_tag_uuid = :iaft_uuid
            """, dict(iaft_uuid=iuaft_rv['identity_album_folder_tag_uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        state:
          - endpoint: {settings.jersey_number_updated_endpoint}
            parameters:
              uniform_album_folder_tag_level_uuid: {iuaft_rv['uniform_album_folder_tag_level_uuid']}
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM identity_uniform_album_folder_tags
            WHERE identity_album_folder_tag_uuid = :iaft_uuid
            """, dict(iaft_uuid=iuaft_rv['identity_album_folder_tag_uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        state: 0
        ''')

    def test_insert_update_delete__without_jersey_number(self):
        with wait_for_cdc(self) as session:
            iuaft_rv = self.df.create_identity_uniform_album_folder_tag(session=session)
        print(iuaft_rv)

        self.assert_rmq_messages(f'''
        error: 0
        state: 0
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE identity_uniform_album_folder_tags SET updated_at = now()
            WHERE identity_album_folder_tag_uuid = :iaft_uuid
            """, dict(iaft_uuid=iuaft_rv['identity_album_folder_tag_uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        state: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM identity_uniform_album_folder_tags
            WHERE identity_album_folder_tag_uuid = :iaft_uuid
            """, dict(iaft_uuid=iuaft_rv['identity_album_folder_tag_uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        state: 0
        ''')


class TestMatchPhotoDeliveriesHandler(CDCTestCase):
    def test_insert_update_delete(self):
        am_rv = self.df.create_albums_membership()

        with wait_for_cdc(self) as session:
            mpd_rv = self.df.create_matched_photo_delivery(status='cleared',
                    session=session,
                    matched_photo_kwargs = {
                      'face_match_vote_kwargs':{
                        'selected_identity_kwargs': {
                          'albums_membership_rv': am_rv
                        }
                      }
                    })
        print(mpd_rv)

        self.assert_rmq_messages(f'''
        error: 0
        notifications:
          - endpoint: {settings.deliver_photo_endpoint}
            parameters:
              matched_photo_delivery_uuid: {mpd_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE matched_photo_deliveries SET updated_at = now()
            WHERE uuid = :mpd_uuid
            """, dict(mpd_uuid=mpd_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        notifications:
          - endpoint: {settings.deliver_photo_endpoint}
            parameters:
              matched_photo_delivery_uuid: {mpd_rv['uuid']}
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM matched_photo_deliveries
            WHERE uuid = :mpd_uuid
            """, dict(mpd_uuid=mpd_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        notifications:
          - endpoint: {settings.deliver_photo_endpoint}
            parameters:
              matched_photo_delivery_uuid: {mpd_rv['uuid']}
        ''')

    def test_insert_update_delete__status_not_right(self):
        am_rv = self.df.create_albums_membership()

        with wait_for_cdc(self) as session:
            mpd_rv = self.df.create_matched_photo_delivery(status='sent',
                    session=session,
                    matched_photo_kwargs = {
                      'face_match_vote_kwargs':{
                        'selected_identity_kwargs': {
                          'albums_membership_rv': am_rv
                        }
                      }
                    })
        print(mpd_rv)

        self.assert_rmq_messages(f'''
        error: 0
        notifications: 0
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE matched_photo_deliveries SET updated_at = now()
            WHERE uuid = :mpd_uuid
            """, dict(mpd_uuid=mpd_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        notifications: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM matched_photo_deliveries
            WHERE uuid = :mpd_uuid
            """, dict(mpd_uuid=mpd_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        notifications: 0
        ''')


class TestMatchedPhotosHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            mp_rv = self.df.create_matched_photo(session=session)
        print(mp_rv)

        self.assert_rmq_messages(f'''
        error: 0
        photo_share_blocker:
          - endpoint: {settings.matched_photo_created_endpoint}
            parameters:
              uuid: {mp_rv['uuid']}
        matched_photo_aggregator:
          # the album_membership and psp endpoints are side effects
          - endpoint: {settings.album_membership_created_endpoint}
          - endpoint: {settings.selected_identity_created_endpoint}
          - endpoint: {settings.matched_photo_created_endpoint}
            parameters:
              matched_photo_uuid: {mp_rv['uuid']}
          - endpoint: {settings.photostream_photo_created_endpoint}
        state:
          - endpoint: {settings.selected_identity_updated_endpoint}
          - endpoint: {settings.matched_photo_updated_endpoint}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE matched_photos SET updated_at = now()
            WHERE uuid = :mp_uuid
            """, dict(mp_uuid=mp_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        photo_share_blocker: 0
        matched_photo_aggregator: 0
        state: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM matched_photos
            WHERE uuid = :mp_uuid
            """, dict(mp_uuid=mp_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        photo_share_blocker:
          - endpoint: {settings.matched_photo_deleted_endpoint}
            parameters:
              uuid: {mp_rv['uuid']}
        matched_photo_aggregator: 0
        state:
          - endpoint: {settings.matched_photo_updated_endpoint}
        ''')


class TestPhotoShareBlocksHandler(CDCTestCase):
    def test_insert_update_delete(self):
        first_psb_rv = self.df.create_photo_share_block()
        photo_rv = self.df.create_photo()

        with wait_for_cdc(self) as session:
            psb_rv = self.df.create_photo_share_block(
                photo_rv=photo_rv,
                identity_rv=first_psb_rv['identity_rv'],
                roster_identity_rv=first_psb_rv['roster_identity_rv'],
                roster_identity_linked_identity_rv=first_psb_rv['roster_identity_linked_identity_rv'],
                session=session
            )
        print(psb_rv)

        self.assert_rmq_messages(f'''
        error: 0
        photo_share_blocker:
          - endpoint: {settings.photo_share_block_created_endpoint}
            parameters:
              uuid: {psb_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE photo_share_blocks SET updated_at = now()
            WHERE uuid = :psb_uuid
            """, dict(psb_uuid=psb_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        photo_share_blocker: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM photo_share_blocks
            WHERE uuid = :psb_uuid
            """, dict(psb_uuid=psb_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        photo_share_blocker:
          - endpoint: {settings.photo_share_block_deleted_endpoint}
            parameters:
              uuid: {psb_rv['uuid']}
        ''')


class TestPhotostreamsPhotosHandler(CDCTestCase):
    def test_insert_update_delete(self):
        first_ap_rv = self.df.create_album_photo()

        with wait_for_cdc(self) as session:
            ap_rv = self.df.create_album_photo(
                    photostream_rv=first_ap_rv['photostreams_photo_rv']['photostream_rv'],
                    album_rv=first_ap_rv['album_rv'],
                    status='published',
                    session=session)
        psp_rv = ap_rv['photostreams_photo_rv']
        psp_uuid = str(psp_rv['uuid'])
        print(ap_rv)

        self.assert_rmq_messages(f'''
        error: 0
        face_surveyor:
          - endpoint: {settings.photo_added_to_album_endpoint}
        slack:
          - endpoint: {settings.photostreams_photos_created_endpoint}
            parameters:
              payload:
                uuid: {psp_uuid}
        photo_router:
          - endpoint: {settings.photostreams_photo_inserted_endpoint}
            parameters:
              uuid: {psp_uuid}
        matched_photo_aggregator:
          - endpoint: {settings.photostream_photo_created_endpoint}
            parameters:
              photostream_photo_uuid: {psp_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE photostreams_photos SET updated_at = now()
            WHERE uuid = :psp_uuid
            """, dict(psp_uuid=psp_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        face_surveyor:
          - endpoint: {settings.photo_added_to_album_endpoint}
        slack: 0
        photo_router: 0
        matched_photo_aggregator: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM photostreams_photos
            WHERE uuid = :psp_uuid
            """, dict(psp_uuid=psp_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        face_surveyor:
          - endpoint: {settings.photo_removed_from_album_endpoint}
        slack: 0
        photo_router:
          - endpoint: {settings.photostreams_photo_inserted_endpoint}
            parameters:
              uuid: {psp_uuid}
              operation: DELETE
        matched_photo_aggregator:
          - endpoint: {settings.photostream_photo_deleted_endpoint}
            parameters:
              photostream_id: {psp_rv['photostream_id']}
              photo_id: {psp_rv['photo_id']}
        ''')

    def test_insert__dnp(self):
        # SETUP:
        # We start with an empty album that has a DNP identity joined.
        # The DNP identity has one active reference_face.
        # We create a new photo with two faces in it (not yet adding it to an album).
        # We create a face_match_vote comparing one of the two photo's faces and the refernece_face.
        # The face_match_vote is a match (vote='positive' and applied=True)
        # This simulates the photo having been removed from the album (we never delete fmvs)
        #
        # ACTION:
        # We add the photo to the album, with 'published' status.
        #
        # EXPECTATIONS:
        # We expect that new dfs rows are added, one per face in photo, all with 'awaiting' status.
        # Since we have a fmv to one of the faces, we expect the dfs row corresponding to that
        # face will be updated to dfs.status='blocked'
        #
        # We expect one adp row was automatically added for the photo following the dfs UPDATE.

        # SETUP:
        with session_scope() as session:
            fmv_rv = self.df.create_face_match_vote(vote='positive',
                    selected_identity_kwargs={'is_dnp_blacklisted': True},
                    applied=True,
                    session=session)
            f1_rv = fmv_rv['compared_face_rv']
            p_rv = f1_rv['photo_rv']
            f2_rv = self.df.create_face(photo_rv=p_rv, session=session)

            si_rv = fmv_rv['selected_identity_rv']
            rf_rv = self.df.create_reference_face(selected_identity_rv=si_rv,
                    face_rv=fmv_rv['selfie_face_rv'],
                    session=session)

            STATEMENT = '''
            DELETE FROM photostreams_photos
            WHERE photo_uuid = :p_uuid
            '''
            session.execute(STATEMENT, dict(p_uuid=p_rv['uuid']))

        with session_scope() as session:
            # because CDC created some dfs rows for us automatically
            STATEMENT = '''
            DELETE FROM dnp_face_statuses
            WHERE identity_uuid = :i_uuid
            '''
            session.execute(STATEMENT, dict(i_uuid=si_rv['identities_uuid']))

        with session_scope() as session:
            # because DB trigger created an adp row automatically
            STATEMENT = '''
            DELETE FROM actionable_dnp_photos
            WHERE photo_uuid = :p_uuid
            '''
            session.execute(STATEMENT, dict(p_uuid=p_rv['uuid']))

        # ACTION:
        a_rv = si_rv['albums_membership_rv']['album_rv']
        ps_rv = a_rv['photostream_rv']
        with wait_for_cdc(self) as session:
            self.df.create_photostreams_photo(
                    status='published',
                    photo_rv=p_rv,
                    photostream_rv=ps_rv,
                    session=session)

        # EXPECTATIONS:
        # expect two dfs rows, one 'awaiting', one 'blocked'
        with session_scope() as session:
            STATEMENT = '''
            SELECT * FROM dnp_face_statuses
            WHERE identity_uuid = :i_uuid
            '''
            results = session.execute(STATEMENT, dict(i_uuid=si_rv['identities_uuid'])).fetchall()
            dfs_by_face = {str(row.compared_face_uuid): row for row in results}
        self.assertTrue(f1_rv['uuid'] in dfs_by_face)
        self.assertEqual(dfs_by_face[f1_rv['uuid']].status, 'blocked')

        self.assertTrue(f2_rv['uuid'] in dfs_by_face)
        self.assertEqual(dfs_by_face[f2_rv['uuid']].status, 'awaiting')

        # expect one adp row
        STATEMENT = '''
        SELECT * FROM actionable_dnp_photos
        WHERE photo_uuid = :p_uuid
        '''
        results = session.execute(STATEMENT, dict(p_uuid=p_rv['uuid'])).fetchall()
        self.assertEqual(len(results), 1)

    def test_delete__dnp(self):
        # SETUP:
        # We start with two albums, sharing a photo with one face in it.
        # A DNP identity is joined to both albums, it has just one active reference_face.
        # There is one dfs row present.
        #
        # FIRST ACTION:
        # We delete the photo from album 1
        #
        # FIRST EXPECTATIONS:
        # We expect the dfs row remains (is not deleted).
        #
        # SECOND ACTION:
        # We delete the photo from album 2
        #
        # SECOND EXPECTATIONS:
        # We expect the dfs row is deleted
        # We further expect an adp row was inserted for the photo.

        # SETUP:
        with session_scope() as session:
            fmv1_rv = self.df.create_face_match_vote(
                    vote='possible',
                    selected_identity_kwargs={'is_dnp_blacklisted': True},
                    session=session)
            f_rv = fmv1_rv['compared_face_rv']
            p_rv = f_rv['photo_rv']
            si1_rv = fmv1_rv['selected_identity_rv']
            i_rv = si1_rv['identity_rv']
            a1_rv = si1_rv['albums_membership_rv']['album_rv']
            ps1_rv = a1_rv['photostream_rv']
            sf_rv = fmv1_rv['selfie_face_rv']
            rf1_rv = self.df.create_reference_face(selected_identity_rv=si1_rv,
                    face_rv=sf_rv,
                    session=session)

            fmv2_rv = self.df.create_face_match_vote(
                    vote='possible',
                    compared_face_rv=f_rv,
                    selected_identity_kwargs={
                        'identity_rv': i_rv,
                        'is_dnp_blacklisted': True,
                    },
                    selfie_face_rv=sf_rv,
                    session=session)
            si2_rv = fmv2_rv['selected_identity_rv']
            a2_rv = si2_rv['albums_membership_rv']['album_rv']
            ps2_rv = a2_rv['photostream_rv']
            self.df.create_photostreams_photo(photostream_rv=ps2_rv,
                    photo_rv=p_rv, session=session)
            rf2_rv = self.df.create_reference_face(selected_identity_rv=si2_rv,
                    face_rv=sf_rv,
                    session=session)

            dfs_rv = self.df.create_dnp_face_status(compared_face_rv=f_rv,
                    identity_rv=i_rv,
                    selfie_face_rv=sf_rv,
                    status='awaiting',
                    session=session)

        print('identity_uuid: %s' % rf1_rv['selected_identity_rv']['identities_uuid'])
        print('photo_uuid: %s' % p_rv['uuid'])
        print('face_uuid: %s' % f_rv['uuid'])
        print('ps1_id: %s' % ps1_rv['id'])

        with session_scope() as session:
            # setup: expect one dfs row
            STATEMENT = '''
            SELECT * FROM dnp_face_statuses
            WHERE identity_uuid = :i_uuid
            '''
            results = session.execute(STATEMENT, dict(i_uuid=si1_rv['identities_uuid'])).fetchall()
            dfs_by_face = {str(row.compared_face_uuid): row for row in results}
            self.assertTrue(len(dfs_by_face), 1)
            self.assertTrue(f_rv['uuid'] in dfs_by_face)

            # setup: expect no adp rows
            STATEMENT = '''
            SELECT * FROM actionable_dnp_photos
            WHERE photo_uuid = :p_uuid
            '''
            results = session.execute(STATEMENT, dict(p_uuid=p_rv['uuid'])).fetchall()
            self.assertEqual(len(results), 0)

        # FIRST ACTION:
        with wait_for_cdc(self) as session:
            STATEMENT = '''
            DELETE FROM photostreams_photos
            WHERE photostream_id = :ps_id
            '''
            session.execute(STATEMENT, dict(ps_id=ps1_rv['id']))

        # FIRST EXPECTATIONS:
        # expect (still) one dfs row
        with session_scope() as session:
            STATEMENT = '''
            SELECT * FROM dnp_face_statuses
            WHERE identity_uuid = :i_uuid
            '''
            results = session.execute(STATEMENT, dict(i_uuid=si1_rv['identities_uuid'])).fetchall()
            dfs_by_face = {str(row.compared_face_uuid): row for row in results}
        self.assertTrue(len(dfs_by_face), 1)
        self.assertTrue(f_rv['uuid'] in dfs_by_face)

        # SECOND ACTION
        a2_rv = si2_rv['albums_membership_rv']['album_rv']
        ps2_rv = a2_rv['photostream_rv']
        with wait_for_cdc(self) as session:
            STATEMENT = '''
            DELETE FROM photostreams_photos
            WHERE photostream_id = :ps_id
            '''
            session.execute(STATEMENT, dict(ps_id=ps2_rv['id']))

        # SECOND EXPECTATIONS:
        with session_scope() as session:
            # expect no dfs rows
            STATEMENT = '''
            SELECT * FROM dnp_face_statuses
            WHERE identity_uuid = :i_uuid
            '''
            results = session.execute(STATEMENT, dict(i_uuid=si1_rv['identities_uuid'])).fetchall()
            self.assertEqual(len(results), 0)

            # setup: expect one adp row
            STATEMENT = '''
            SELECT * FROM actionable_dnp_photos
            WHERE photo_uuid = :p_uuid
            '''
            results = session.execute(STATEMENT, dict(p_uuid=p_rv['uuid'])).fetchall()
            self.assertEqual(len(results), 1)

    def test_insert_update_delete__dnp_identity_subscribed__published(self):
        first_ap_rv = self.df.create_album_photo()
        # we need a subscribed dnp identity
        dnp_si_rv = self.df.create_selected_identity(is_dnp_blacklisted=True,
                albums_membership_kwargs={'album_rv': first_ap_rv['album_rv']})
        # and for the photo to have a face in it
        f_rv = self.df.create_face()
        # and finally, we need the identity to have a reference_face in this album
        rf_rv = self.df.create_reference_face(selected_identity_rv=dnp_si_rv,
                face_rv=f_rv)

        with wait_for_cdc(self) as session:
            ap_rv = self.df.create_album_photo(
                    photostream_rv=first_ap_rv['photostreams_photo_rv']['photostream_rv'],
                    album_rv=first_ap_rv['album_rv'],
                    photo_rv=f_rv['photo_rv'],
                    status='published',
                    session=session)
        psp_rv = ap_rv['photostreams_photo_rv']
        psp_uuid = str(psp_rv['uuid'])
        print(ap_rv)

        # this is tricky... cdc processing of just the INSERT would leave out
        # messages to face-surveyor, BUT dnp processing UPDATEs the psp,
        # so you have to account for the messages sent during the update as well here.
        self.assert_rmq_messages(f'''
        error: 0
        face_surveyor:
          - endpoint: {settings.photo_added_to_album_endpoint}
        slack:
          - endpoint: {settings.photostreams_photos_created_endpoint}
            parameters:
              payload:
                uuid: {psp_uuid}
        photo_router:
          - endpoint: {settings.photostreams_photo_inserted_endpoint}
            parameters:
              uuid: {psp_uuid}
              operation: INSERT
        matched_photo_aggregator:
          - endpoint: {settings.photostream_photo_updated_endpoint}
        ''')

        with session_scope() as session:
            rows = session.execute("""
            SELECT *
            FROM dnp_face_statuses
            WHERE identity_uuid = :i_uuid
            """, dict(i_uuid=dnp_si_rv['identities_uuid'])).fetchall()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(str(row.compared_face_uuid), f_rv['uuid'])
            self.assertEqual(row.status, 'awaiting')

            rows = session.execute("""
            SELECT *
            FROM dnp_photostreams_photos
            WHERE photostreams_photo_uuid = :psp_uuid
            """, dict(psp_uuid=psp_uuid)).fetchall()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.clear_status, 'published')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE photostreams_photos SET updated_at = now()
            WHERE uuid = :psp_uuid
            """, dict(psp_uuid=psp_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        face_surveyor:
          - endpoint: {settings.photo_added_to_album_endpoint}
        slack: 0
        photo_router: 0
        matched_photo_aggregator: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM photostreams_photos
            WHERE uuid = :psp_uuid
            """, dict(psp_uuid=psp_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        face_surveyor:
          - endpoint: {settings.photo_removed_from_album_endpoint}
        slack: 0
        photo_router:
          - endpoint: {settings.photostreams_photo_inserted_endpoint}
            parameters:
              uuid: {psp_uuid}
              operation: DELETE
        matched_photo_aggregator:
          - endpoint: {settings.photostream_photo_deleted_endpoint}
        ''')

    def test_insert_update_delete__dnp_identity_subscribed__reviewing(self):
        first_ap_rv = self.df.create_album_photo()
        # we need a subscribed dnp identity
        dnp_si_rv = self.df.create_selected_identity(is_dnp_blacklisted=True,
                albums_membership_kwargs={'album_rv': first_ap_rv['album_rv']})
        # and for the photo to have a face in it
        f_rv = self.df.create_face()
        # and finally, we need the identity to have a reference_face in this album
        rf_rv = self.df.create_reference_face(selected_identity_rv=dnp_si_rv,
                face_rv=f_rv)

        with wait_for_cdc(self) as session:
            ap_rv = self.df.create_album_photo(
                    photostream_rv=first_ap_rv['photostreams_photo_rv']['photostream_rv'],
                    album_rv=first_ap_rv['album_rv'],
                    photo_rv=f_rv['photo_rv'],
                    status='reviewing',
                    session=session)
        psp_rv = ap_rv['photostreams_photo_rv']
        psp_uuid = str(psp_rv['uuid'])
        print(ap_rv)

        # this is tricky... cdc processing of just the INSERT would leave out
        # messages to face-surveyor and photo-router, BUT dnp processing UPDATEs the psp,
        # so you have to account for the messages sent during the update as well here.
        self.assert_rmq_messages(f'''
        error: 0
        face_surveyor:
          - endpoint: {settings.photo_added_to_album_endpoint}
        slack:
          - endpoint: {settings.photostreams_photos_created_endpoint}
            parameters:
              payload:
                uuid: {psp_uuid}
        photo_router:
          - endpoint: {settings.photostreams_photo_inserted_endpoint}
            parameters:
              uuid: {psp_uuid}
              operation: INSERT
        matched_photo_aggregator:
          - endpoint: {settings.photostream_photo_updated_endpoint}
        ''')

        with session_scope() as session:
            rows = session.execute("""
            SELECT *
            FROM dnp_face_statuses
            WHERE identity_uuid = :i_uuid
            """, dict(i_uuid=dnp_si_rv['identities_uuid'])).fetchall()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(str(row.compared_face_uuid), f_rv['uuid'])
            self.assertEqual(row.status, 'awaiting')

            rows = session.execute("""
            SELECT *
            FROM dnp_photostreams_photos
            WHERE photostreams_photo_uuid = :psp_uuid
            """, dict(psp_uuid=psp_uuid)).fetchall()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.clear_status, 'reviewing')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE photostreams_photos SET updated_at = now()
            WHERE uuid = :psp_uuid
            """, dict(psp_uuid=psp_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        face_surveyor:
          - endpoint: {settings.photo_added_to_album_endpoint}
        slack: 0
        photo_router: 0
        matched_photo_aggregator: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM photostreams_photos
            WHERE uuid = :psp_uuid
            """, dict(psp_uuid=psp_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        face_surveyor:
          - endpoint: {settings.photo_removed_from_album_endpoint}
        slack: 0
        photo_router:
          - endpoint: {settings.photostreams_photo_inserted_endpoint}
            parameters:
              uuid: {psp_uuid}
              operation: DELETE
        matched_photo_aggregator:
          - endpoint: {settings.photostream_photo_deleted_endpoint}
        ''')

    def test_insert__duplicate_image_in_album(self):
        i_rv = self.df.create_image()
        first_ap_rv = self.df.create_album_photo(photo_kwargs={'image_rv': i_rv})

        with wait_for_cdc(self) as session:
            ap_rv = self.df.create_album_photo(
                    photostream_rv=first_ap_rv['photostreams_photo_rv']['photostream_rv'],
                    album_rv=first_ap_rv['album_rv'],
                    photo_kwargs={'image_rv': i_rv},
                    status='published',
                    session=session)
        psp_rv = ap_rv['photostreams_photo_rv']
        psp_uuid = str(psp_rv['uuid'])
        print(ap_rv)

        # This is tricky, there should be no rmq messages for the INSERT, but because it's a duplicate
        # we DELETE it, so that does emit rmq messages to remove the photo
        self.assert_rmq_messages(f'''
        error: 0
        face_surveyor:
          - endpoint: {settings.photo_removed_from_album_endpoint}
        slack: 0
        photo_router:
          - endpoint: {settings.photostreams_photo_inserted_endpoint}
            parameters:
              uuid: {psp_uuid}
              operation: DELETE
        matched_photo_aggregator:
          - endpoint: {settings.photostream_photo_deleted_endpoint}
        ''')

        with session_scope() as session:
            psp_info = session.execute("""
            SELECT * FROM photostreams_photos
            WHERE uuid = :psp_uuid
            """, dict(psp_uuid=psp_uuid)).fetchone()
            self.assertTrue(psp_info is None)

    def test_update__awaiting_matched_photos(self):
        f_rv = self.df.create_face()
        ap_rv = self.df.create_album_photo(
                status='awaiting-dnp-clearance',
                photo_rv=f_rv['photo_rv'])
        mp_rv = self.df.create_matched_photo(
            status='awaiting-dnp-clearance',
            face_match_vote_kwargs={
                'selected_identity_kwargs': {
                    'albums_membership_kwargs': {
                        'album_rv': ap_rv['album_rv']
                    },
                },
                'compared_face_rv': f_rv
            }
        )
        mpd_rv = self.df.create_matched_photo_delivery(
                matched_photo_rv=mp_rv,
                status='awaiting-dnp-clearance')

        psp_rv = ap_rv['photostreams_photo_rv']
        psp_uuid = str(psp_rv['uuid'])
        print(ap_rv)

        self.assertEqual(psp_rv['photo_uuid'], mp_rv['photos_uuid'])

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE photostreams_photos SET status = 'published'
            WHERE uuid = :psp_uuid
            """, dict(psp_uuid=psp_uuid))

        self.assert_rmq_messages(f'''
        error: 0
        face_surveyor:
          - endpoint: {settings.photo_added_to_album_endpoint}
        slack: 0
        photo_router: 0
        matched_photo_aggregator:
          - endpoint: {settings.photostream_photo_updated_endpoint}
            parameters:
              photostream_id: {psp_rv['photostream_id']}
              photo_id: {psp_rv['photo_id']}
        ''')

        with session_scope() as session:
            updated_mp = session.execute("""
            SELECT * FROM matched_photos
            WHERE uuid = :mp_uuid
            """, dict(mp_uuid=mp_rv['uuid'])).fetchone()
            self.assertEqual(updated_mp.status, 'cleared')

            mpds = session.execute("""
            SELECT * FROM matched_photo_deliveries
            WHERE matched_photo_uuid = :mp_uuid
            """, dict(mp_uuid=mp_rv['uuid'])).fetchall()
            self.assertTrue(len(mpds), 1)
            mpd = mpds[0]
            self.assertEqual(mpd.status, 'cleared')


class TestPubCommanderingIdentitiesHandler(CDCTestCase):
    def test_insert_update_delete(self):
        si_rv = self.df.create_selected_identity()

        with wait_for_cdc(self) as session:
            pci_rv = self.df.create_pub_commandering_identity(selected_identity_rv=si_rv,
                                                              needs_commandering=False,
                                                              session=session)
        print(pci_rv)

        self.assert_rmq_messages(f'''
        error: 0
        slack:
          - endpoint: {settings.pub_commandering_identity_created_endpoint}
            parameters:
              uuid: {pci_rv['uuid']}
        ''')

        # test an UPDATE that does NOT set needs_commandering to True
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE pub_commandering_identities SET updated_at = now()
            WHERE uuid = :pci_uuid
            """, dict(pci_uuid=pci_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        slack: 0
        ''')

        # test an UPDATE that DOES set needs_commandering to True
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE pub_commandering_identities SET updated_at = now(), needs_commandering = true
            WHERE uuid = :pci_uuid
            """, dict(pci_uuid=pci_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        slack:
          - endpoint: {settings.pub_commandering_identity_updated_endpoint}
            parameters:
              uuid: {pci_rv['uuid']}
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM pub_commandering_identities
            WHERE uuid = :pci_uuid
            """, dict(pci_uuid=pci_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        slack:
          - endpoint: {settings.pub_commandering_identity_deleted_endpoint}
            parameters:
              uuid: {pci_rv['uuid']}
        ''')


class TestPurchasedAlbumFoldersIdentitiesHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            pafi_rv = self.df.create_purchased_album_folders_identity(session=session)
        print(pafi_rv)

        self.assert_rmq_messages(f'''
        error: 0
        hive_next:
          - endpoint: {settings.purchased_album_folder_identity_created_endpoint}
            parameters:
              payload:
                uuid: {pafi_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE purchased_album_folders_identities SET updated_at = now()
            WHERE uuid = :pafi_uuid
            """, dict(pafi_uuid=pafi_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM purchased_album_folders_identities
            WHERE uuid = :pafi_uuid
            """, dict(pafi_uuid=pafi_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        ''')


class TestPurchasedAlbumsIdentitiesHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            pai_rv = self.df.create_purchased_albums_identity(session=session)
        print(pai_rv)

        self.assert_rmq_messages(f'''
        error: 0
        hive_next:
          - endpoint: {settings.purchased_album_identity_created_endpoint}
            parameters:
              payload:
                uuid: {pai_rv['uuid']}
        matched_photo_aggregator:
          - endpoint: {settings.purchased_album_identity_created_endpoint}
            parameters:
              purchased_album_uuid: {pai_rv['purchased_albums_uuid']}
              identity_uuid: {pai_rv['identities_uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE purchased_albums_identities SET updated_at = now()
            WHERE uuid = :pai_uuid
            """, dict(pai_uuid=pai_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        matched_photo_aggregator: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM purchased_albums_identities
            WHERE uuid = :pai_uuid
            """, dict(pai_uuid=pai_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        matched_photo_aggregator: 0
        ''')


class TestRosterIdentityLinkedIdentitiesHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            rili_rv = self.df.create_roster_identity_linked_identity(session=session)
        print(rili_rv)

        self.assert_rmq_messages(f'''
        error: 0
        photo_share_blocker:
          - endpoint: {settings.roster_identity_linked_identity_created_endpoint}
            parameters:
                uuid: {rili_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE roster_identity_linked_identities SET updated_at = now()
            WHERE uuid = :rili_uuid
            """, dict(rili_uuid=rili_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        photo_share_blocker:
          - endpoint: {settings.roster_identity_linked_identity_updated_endpoint}
            parameters:
                uuid: {rili_rv['uuid']}
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM roster_identity_linked_identities
            WHERE uuid = :rili_uuid
            """, dict(rili_uuid=rili_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        photo_share_blocker: 0
        ''')


class TestSelectedIdentityLinksHandler(CDCTestCase):
    def test_insert_update_delete__master(self):
        si_rv = self.df.create_selected_identity()

        with wait_for_cdc(self) as session:
            sil_rv = self.df.create_selected_identity_link(
                    selected_identity_rv=si_rv,
                    is_master=True,
                    session=session)
        print(sil_rv)

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        reference_face_coordinator:
          - endpoint: {settings.selected_identity_link_updated_endpoint}
            parameters:
              operation: 'INSERT'
              selected_identity_uuid: {sil_rv['selected_identity_uuid']}
        face_matcher:
          - endpoint: {settings.selected_identity_link_updated_endpoint}
            parameters:
              selected_identity_uuid: {sil_rv['selected_identity_uuid']}
              roster_identity_uuid: {sil_rv['roster_identity_uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE selected_identity_links SET updated_at = now()
            WHERE selected_identity_uuid = :si_uuid
            """, dict(si_uuid=sil_rv['selected_identity_uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        reference_face_coordinator:
          - endpoint: {settings.selected_identity_link_updated_endpoint}
            parameters:
              operation: 'UPDATE'
              selected_identity_uuid: {sil_rv['selected_identity_uuid']}
        face_matcher:
          - endpoint: {settings.selected_identity_link_updated_endpoint}
            parameters:
              selected_identity_uuid: {sil_rv['selected_identity_uuid']}
              roster_identity_uuid: {sil_rv['roster_identity_uuid']}
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM selected_identity_links
            WHERE selected_identity_uuid = :si_uuid
            """, dict(si_uuid=sil_rv['selected_identity_uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next:
          - endpoint: {settings.selected_identity_link_deleted_endpoint}
            parameters:
              selected_identity_uuid: {sil_rv['selected_identity_uuid']}
        reference_face_coordinator:
          - endpoint: {settings.selected_identity_link_updated_endpoint}
            parameters:
              operation: 'DELETE'
              selected_identity_uuid: {sil_rv['selected_identity_uuid']}
        face_matcher: 0
        ''')

    def test_insert_update_delete__not_master(self):
        si_rv = self.df.create_selected_identity()

        with wait_for_cdc(self) as session:
            sil_rv = self.df.create_selected_identity_link(
                    selected_identity_rv=si_rv,
                    is_master=False,
                    session=session)
        print(sil_rv)

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        reference_face_coordinator:
          - endpoint: {settings.selected_identity_link_updated_endpoint}
            parameters:
              operation: 'INSERT'
              selected_identity_uuid: {sil_rv['selected_identity_uuid']}
        face_matcher:
          - endpoint: {settings.selected_identity_link_updated_endpoint}
            parameters:
              selected_identity_uuid: {sil_rv['selected_identity_uuid']}
              roster_identity_uuid: {sil_rv['roster_identity_uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE selected_identity_links SET updated_at = now()
            WHERE selected_identity_uuid = :si_uuid
            """, dict(si_uuid=sil_rv['selected_identity_uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        reference_face_coordinator:
          - endpoint: {settings.selected_identity_link_updated_endpoint}
            parameters:
              operation: 'UPDATE'
              selected_identity_uuid: {sil_rv['selected_identity_uuid']}
        face_matcher:
          - endpoint: {settings.selected_identity_link_updated_endpoint}
            parameters:
              selected_identity_uuid: {sil_rv['selected_identity_uuid']}
              roster_identity_uuid: {sil_rv['roster_identity_uuid']}
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM selected_identity_links
            WHERE selected_identity_uuid = :si_uuid
            """, dict(si_uuid=sil_rv['selected_identity_uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        reference_face_coordinator:
          - endpoint: {settings.selected_identity_link_updated_endpoint}
            parameters:
              operation: 'DELETE'
              selected_identity_uuid: {sil_rv['selected_identity_uuid']}
        face_matcher: 0
        ''')


class TestSubscribedAlbumFoldersIdentities(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            safi_rv = self.df.create_subscribed_album_folders_identity(session=session)
        print(safi_rv)

        self.assert_rmq_messages(f'''
        error: 0
        hive_next:
          - endpoint: {settings.subscribed_album_folder_identity_created_endpoint}
            parameters:
              payload:
                uuid: {safi_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE subscribed_album_folders_identities SET updated_at = now()
            WHERE uuid = :safi_uuid
            """, dict(safi_uuid=safi_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM subscribed_album_folders_identities
            WHERE uuid = :safi_uuid
            """, dict(safi_uuid=safi_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        hive_next: 0
        ''')


class TestTransactionRefundsHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            tr_rv = self.df.create_transaction_refund(session=session)
        print(tr_rv)

        self.assert_rmq_messages(f'''
        error: 0
        slack:
          - endpoint: {settings.transaction_refund_created_endpoint}
            parameters:
              payload:
                uuid: {tr_rv['uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE transaction_refunds SET updated_at = now()
            WHERE uuid = :tr_uuid
            """, dict(tr_uuid=tr_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        slack: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM transaction_refunds
            WHERE uuid = :tr_uuid
            """, dict(tr_uuid=tr_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        slack: 0
        ''')


class TestWatermarkConfigHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            wc_rv = self.df.create_watermark_config(session=session)
        print(wc_rv)

        self.assert_rmq_messages(f'''
        error: 0
        photo_prep:
          - endpoint: {settings.watermark_config_updated_endpoint}
            parameters:
              uuid: {wc_rv['watermark_config_uuid']}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE watermark_config SET updated_at = now()
            WHERE watermark_config_uuid = :wc_uuid
            """, dict(wc_uuid=wc_rv['watermark_config_uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        photo_prep:
          - endpoint: {settings.watermark_config_updated_endpoint}
            parameters:
              uuid: {wc_rv['watermark_config_uuid']}
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM watermark_config
            WHERE watermark_config_uuid = :wc_uuid
            """, dict(wc_uuid=wc_rv['watermark_config_uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        photo_prep: 0
        ''')


class TestSelectedIdentitiesHandler(CDCTestCase):
    def test_insert_update_delete(self):
        f_rv = self.df.create_face()
        ap_rv = self.df.create_album_photo(
                photo_rv=f_rv['photo_rv'],
                status='published')

        with wait_for_cdc(self) as session:
            si_rv = self.df.create_selected_identity(is_dnp_blacklisted=False,
                    albums_membership_kwargs={'album_rv': ap_rv['album_rv']},
                    session=session)
        print(si_rv)

        self.assert_rmq_messages(f'''
        error: 0
        hive_next:
          - endpoint: {settings.selected_identity_created_endpoint}
            parameters:
              uuid: {si_rv['uuid']}
        slack:
          - endpoint: {settings.selected_identity_created_endpoint}
            parameters:
              payload:
                uuid: {si_rv['uuid']}
        state:
          - endpoint: {settings.selected_identity_updated_endpoint}
            parameters:
              uuid: {si_rv['uuid']}
              operation: 'INSERT'
        matched_photo_aggregator:
          # side effect from creating the selected identity
          - endpoint: {settings.album_membership_created_endpoint}
          - endpoint: {settings.selected_identity_created_endpoint}
            parameters:
              identity_uuid: {si_rv['identity_rv']['uuid']}
              album_membership_uuid: {si_rv['albums_membership_rv']['uuid']}
        ''')

        with session_scope() as session:
            rows = session.execute("""
            SELECT *
            FROM photostreams_photos
            WHERE photostream_id = :ps_id
            """, dict(ps_id=ap_rv['photostreams_photo_rv']['photostream_id'])).fetchall()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.status, 'published')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE selected_identities SET updated_at = now()
            WHERE uuid = :si_uuid
            """, dict(si_uuid=si_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        state: 0
        matched_photo_aggregator: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE FROM selected_identities
            WHERE uuid = :si_uuid
            """, dict(si_uuid=si_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        state:
          - endpoint: {settings.selected_identity_updated_endpoint}
            parameters:
              uuid: {si_rv['uuid']}
              operation: 'DELETE'
        matched_photo_aggregator: 0
        ''')

    def test_insert_invitee(self):
        f_rv = self.df.create_face()
        ap_rv = self.df.create_album_photo(
                photo_rv=f_rv['photo_rv'],
                status='published')

        with wait_for_cdc(self) as session:
            si_rv = self.df.create_selected_identity(is_dnp_blacklisted=False,
                    is_invitee=True,
                    albums_membership_kwargs={'album_rv': ap_rv['album_rv']},
                    session=session)
        print(si_rv)

        self.assert_rmq_messages(f'''
        error: 0
        hive_next:
          - endpoint: {settings.selected_identity_created_endpoint}
        slack:
          - endpoint: {settings.selected_identity_created_endpoint}
        state:
          - endpoint: {settings.selected_identity_updated_endpoint}
        matched_photo_aggregator:
          # only the side effect message was sent
          - endpoint: {settings.album_membership_created_endpoint}
        ''')

class TestAlbumTagsUpdatedHandlers(CDCTestCase):
    def test_creating_player(self):
        with wait_for_cdc(self) as session:
            player_rv = self.df.create_player(jersey_number=42, colors=['black', 'red'],
                    session=session)
        auaftlj_rv = player_rv['album_uniform_album_folder_tag_level_jersey_rv']
        auaftl_rv = auaftlj_rv['album_uniform_album_folder_tag_level_rv']
        album_uuid = auaftl_rv['album_album_folder_tag_rv']['album_uuid']
        print(player_rv)

        self.assert_rmq_messages(f'''
        error: 0
        state:
          - endpoint: {settings.jersey_number_updated_endpoint}
          - endpoint: {settings.selected_identity_updated_endpoint}
        photo_router:
          # one from the album_album_folder_tag
          - endpoint: {settings.album_tags_updated_endpoint}
            parameters:
              album_uuid: {album_uuid}
          # another one from the uniform_album_folder_tag
          - endpoint: {settings.album_tags_updated_endpoint}
            parameters:
              album_uuid: {album_uuid}
        ''')


class TestPurchasedPhotosHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            pp_rv = self.df.create_purchased_photo(session=session)
        print(pp_rv)

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator:
          - endpoint: {settings.purchased_photo_created_endpoint}
            parameters:
              account_id: {pp_rv['account_rv']['id']}
              photo_id: {pp_rv['photo_rv']['id']}
          # side effect from creating the psp
          - endpoint: {settings.photostream_photo_created_endpoint}
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE purchased_photos SET updated_at = now()
            WHERE uuid = :pp_uuid
            """, dict(pp_uuid=pp_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE from purchased_photos
            WHERE uuid = :pp_uuid
            """, dict(pp_uuid=pp_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator: 0
        ''')


class TestAccountsHandler(CDCTestCase):
    def test_insert_update_delete(self):
        with wait_for_cdc(self) as session:
            a_rv = self.df.create_account(session=session)
        print(a_rv)

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator: 0
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE accounts SET updated_at = now()
            WHERE uuid = :a_uuid
            """, dict(a_uuid=a_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator: 0
        ''')

        # test a DELETE
        with wait_for_cdc(self) as session:
            session.execute("""
            DELETE from accounts
            WHERE uuid = :a_uuid
            """, dict(a_uuid=a_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator: 0
        ''')

    def test_soft_delete(self):
        with wait_for_cdc(self) as session:
            a_rv = self.df.create_account(soft_deleted=True, session=session)
        print(a_rv)

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator: 0
        ''')

        # test an UPDATE
        with wait_for_cdc(self) as session:
            session.execute("""
            UPDATE accounts SET soft_deleted = false
            WHERE uuid = :a_uuid
            """, dict(a_uuid=a_rv['uuid']))

        self.assert_rmq_messages(f'''
        error: 0
        matched_photo_aggregator:
          - endpoint: {settings.account_updated_endpoint}
            parameters:
              account_uuid: {a_rv['uuid']}
              soft_deleted: {False}
        ''')
