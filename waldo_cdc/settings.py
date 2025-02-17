from waldo_common.settings.base import Settings, Env


class ServiceSettings(Settings):
    account_updated_endpoint = Env(default='account_updated')
    album_created_endpoint = Env(default='album_created')
    album_folder_member_created_endpoint = Env(default='album_folder_member_created')
    album_folder_share_created_endpoint = Env(default='album_folder_share_created')
    album_folder_share_updated_endpoint = Env(default='album_folder_share_updated')
    album_membership_status_endpoint = Env(default='album_membership_status')
    album_membership_created_endpoint = Env(default='album_membership_created')
    album_membership_updated_endpoint = Env(default='album_membership_updated')
    album_share_updated_endpoint = Env(default='album_share_updated')
    album_tags_updated_endpoint = Env(default='album_tags_updated')
    album_updated_endpoint = Env(default='album_updated')
    auth_phone_verification_created_endpoint = Env(default='auth_phone_verification_created')
    deliver_photo_endpoint = Env(default='deliver_photo')
    face_group_content_endpoint = Env(default='face_group_content')
    face_match_vote_updated_endpoint = Env(default='face_match_vote_updated')
    jersey_number_updated_endpoint = Env(default='jersey_number_updated')
    matched_photo_created_endpoint = Env(default='matched_photo_created')
    matched_photo_deleted_endpoint = Env(default='matched_photo_deleted')
    matched_photo_updated_endpoint = Env(default='matched_photo_updated')
    photo_added_to_album_endpoint = Env(default='photo_added_to_album')
    photo_share_block_created_endpoint = Env(default='photo_share_block_created')
    photo_share_block_deleted_endpoint = Env(default='photo_share_block_deleted')
    photo_removed_from_album_endpoint = Env(default='photo_removed_from_album')
    photostreams_photo_inserted_endpoint = Env(default='photostreams_photo_inserted')
    photostreams_photos_created_endpoint = Env(default='photostreams_photos_created')
    photostream_photo_created_endpoint = Env(default='photostream_photo_created')
    photostream_photo_deleted_endpoint = Env(default='photostream_photo_deleted')
    photostream_photo_updated_endpoint = Env(default='photostream_photo_updated')
    pub_commandering_identity_created_endpoint = Env(default='pub_commandering_identity_created')
    pub_commandering_identity_deleted_endpoint = Env(default='pub_commandering_identity_deleted')
    pub_commandering_identity_updated_endpoint = Env(default='pub_commandering_identity_updated')
    purchased_album_folder_identity_created_endpoint = Env(default='purchased_album_folder_identity_created')
    purchased_album_identity_created_endpoint = Env(default='purchased_album_identity_created')
    purchased_photo_created_endpoint = Env(default='purchased_photo_created')
    roster_identity_linked_identity_created_endpoint = Env(default='roster_identity_linked_identity_created')
    roster_identity_linked_identity_updated_endpoint = Env(default='roster_identity_linked_identity_updated')
    selected_identity_link_deleted_endpoint = Env(default='selected_identity_link_deleted')
    selected_identity_link_updated_endpoint = Env(default='selected_identity_link_updated')
    subscribed_album_folder_identity_created_endpoint = Env(default='subscribed_album_folder_identity_created')
    transaction_refund_created_endpoint = Env(default='transaction_refund_created')
    watermark_config_updated_endpoint = Env(default='watermark_config_updated')
    selected_identity_updated_endpoint = Env(default='selected_identity_updated')
    selected_identity_created_endpoint = Env(default='selected_identity_created')
    process_dnp_album_endpoint = Env(default='process_dnp_album')
    time_based_matching_enabled_endpoint = Env(default='time_based_matching_enabled')


    comms_routing_key = Env()
    error_routing_key = Env()
    face_surveyor_routing_key = Env()
    face_matcher_routing_key = Env()
    health_check_routing_key = Env(default='zabbix-hive-pg-test')
    hive_next_routing_key = Env()
    notifications_routing_key = Env()
    matched_photo_aggregator_routing_key = Env()
    photo_prep_routing_key = Env()
    photo_router_routing_key = Env()
    photo_share_blocker_routing_key = Env()
    reference_face_coordinator_routing_key = Env()
    slack_routing_key = Env()
    state_routing_key = Env()
    time_matcher_routing_key = Env()
    max_priority = Env(cast=int, default=10)
    general_priority = Env(cast=int, default=3)
    selfie_priority = Env(cast=int, default=6)
    reprocessing_priority = Env(cast=int, default=0)

settings = ServiceSettings()
