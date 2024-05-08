ALTER TABLE waldo.cdc_events ENABLE TRIGGER notify_on_new_cdc_event;
ALTER TABLE waldo.album_folder_shares ENABLE TRIGGER write_to_cdc_events__album_folder_shares;
ALTER TABLE waldo.album_folders_members ENABLE TRIGGER write_to_cdc_events__album_folders_members;
ALTER TABLE waldo.albums ENABLE TRIGGER write_to_cdc_events__albums;
ALTER TABLE waldo.album_shares ENABLE TRIGGER write_to_cdc_events__album_shares;
ALTER TABLE waldo.albums_memberships ENABLE TRIGGER write_to_cdc_events__albums_memberships;
ALTER TABLE waldo.auth_phone_verifications ENABLE TRIGGER write_to_cdc_events__auth_phone_verifications;
ALTER TABLE waldo.face_match_votes ENABLE TRIGGER write_to_cdc_events__face_match_votes;
ALTER TABLE waldo.health_check ENABLE TRIGGER write_to_cdc_events__health_check;
ALTER TABLE waldo.identity_uniform_album_folder_tags ENABLE TRIGGER write_to_cdc_events__identity_uniform_album_folder_tags;
ALTER TABLE waldo.matched_photo_deliveries ENABLE TRIGGER write_to_cdc_events__matched_photo_deliveries;
ALTER TABLE waldo.matched_photos ENABLE TRIGGER write_to_cdc_events__matched_photos;
ALTER TABLE waldo.photo_share_blocks ENABLE TRIGGER write_to_cdc_events__photo_share_blocks;
ALTER TABLE waldo.photostreams_photos ENABLE TRIGGER write_to_cdc_events__photostreams_photos;
ALTER TABLE waldo.pub_commandering_identities ENABLE TRIGGER write_to_cdc_events__pub_commandering_identities;
ALTER TABLE waldo.purchased_album_folders_identities ENABLE TRIGGER write_to_cdc_events__purchased_album_folders_identities;
ALTER TABLE waldo.purchased_albums_identities ENABLE TRIGGER write_to_cdc_events__purchased_albums_identities;
ALTER TABLE waldo.roster_identity_linked_identities ENABLE TRIGGER write_to_cdc_events__roster_identity_linked_identities;
ALTER TABLE waldo.selected_identities ENABLE TRIGGER write_to_cdc_events__selected_identities;
ALTER TABLE waldo.selected_identity_links ENABLE TRIGGER write_to_cdc_events__selected_identity_links;
ALTER TABLE waldo.subscribed_album_folders_identities ENABLE TRIGGER write_to_cdc_events__subscribed_album_folders_identities;
ALTER TABLE waldo.transaction_refunds ENABLE TRIGGER write_to_cdc_events__transaction_refunds;
ALTER TABLE waldo.watermark_config ENABLE TRIGGER write_to_cdc_events__watermark_config;
ALTER TABLE waldo.purchased_photos ENABLE TRIGGER write_to_cdc_events__purchased_photos;
ALTER TABLE waldo.accounts ENABLE TRIGGER write_to_cdc_events__accounts;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'write_to_cdc_events__album_album_folder_tags') THEN
        CREATE TRIGGER write_to_cdc_events__album_album_folder_tags AFTER INSERT OR UPDATE OR DELETE ON waldo.album_album_folder_tags
        FOR EACH ROW EXECUTE PROCEDURE waldo.write_to_cdc_events();
        ALTER TABLE waldo.album_album_folder_tags ENABLE TRIGGER write_to_cdc_events__album_album_folder_tags;
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'write_to_cdc_events__uniform_album_folder_tags') THEN
        CREATE TRIGGER write_to_cdc_events__uniform_album_folder_tags AFTER INSERT OR UPDATE OR DELETE ON waldo.uniform_album_folder_tags
        FOR EACH ROW EXECUTE PROCEDURE waldo.write_to_cdc_events();
        ALTER TABLE waldo.uniform_album_folder_tags ENABLE TRIGGER write_to_cdc_events__uniform_album_folder_tags;
    END IF;
END
$$;
