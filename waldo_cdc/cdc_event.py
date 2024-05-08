import json

class CDCEvent:
    def __init__(self, event_id, table_name, operation_name, created_at,
            prior_row_data=None,
            row_data_updates=None,
            is_processed=False,
            error_message=None,
            updated_at=None):
        self.event_id = event_id
        self.table_name = table_name
        self.operation_name = operation_name
        self.created_at = created_at

        self.prior_row_data = prior_row_data
        self.row_data_updates = row_data_updates
        self.is_processed = is_processed
        self.error_message = error_message
        self.updated_at = updated_at

        self.is_insert = operation_name.lower() == 'insert'
        self.is_update = operation_name.lower() == 'update'
        self.is_delete = operation_name.lower() == 'delete'
        self.reduce_row_data_updates()

    def reduce_row_data_updates(self):
        """
        Deletes keys from self.row_data_updates if values are duplicated from self.prior_row_data
        """
        if self.prior_row_data is None or self.row_data_updates is None:
            return

        keys_to_delete = []
        for uk, uv in self.row_data_updates.items():
            if self.prior_row_data[uk] == uv:
                keys_to_delete.append(uk)

        for key in keys_to_delete:
            del self.row_data_updates[key]

    @classmethod
    def from_row(cls, event_dict):
        kwargs = {**event_dict, 'event_id': event_dict['id']}
        del kwargs['id']

        if kwargs['prior_row_data'] is not None:
            kwargs['prior_row_data'] = json.loads(kwargs['prior_row_data'])

        if kwargs['row_data_updates'] is not None:
            kwargs['row_data_updates'] = json.loads(kwargs['row_data_updates'])

        return cls(**kwargs)

    def to_dict_for_logging(self):
        result = {
            'event_id': self.event_id,
            'table_name': self.table_name,
            'operation_name': self.operation_name,
            'created_at': self.created_at.isoformat(),
            'is_processed': self.is_processed}

        if self.row_data_updates is not None:
            result['row_data_updates'] = json.dumps(self.row_data_updates, sort_keys=True)
        else:
            result['prior_row_data'] = json.dumps(self.prior_row_data, sort_keys=True)

        if self.error_message is not None:
            result['error_message'] = self.error_message

        if self.updated_at is not None:
            result['updated_at'] = self.updated_at.isoformat()

        return result

    def field_was_updated(self, field_name):
        if self.row_data_updates is None:
            return False
        else:
            return field_name in self.row_data_updates

    def get_row_data_value(self, column_name):
        if self.row_data_updates is not None:
            if self.prior_row_data is not None:
                return self.row_data_updates.get(column_name, self.prior_row_data[column_name])
            else:
                return self.row_data_updates[column_name]
        else:
            return self.prior_row_data[column_name]

    def get_legacy_payload(self):
        if self.is_insert:
            return self.row_data_updates
        elif self.is_update:
            payload = {}
            for key in self.prior_row_data.keys():
                payload[key] = self.get_row_data_value(key)
            return payload
        elif self.is_delete:
            return self.prior_row_data

    def get_update_statement_and_args(self):
        args = [self.event_id, self.error_message]
        if self.is_update:
            UPDATE_STATEMENT = """
            UPDATE cdc_events SET is_processed=true,
                                  updated_at=now(),
                                  row_data_updates=$3,
                                  error_message=$2
            WHERE id=$1
            RETURNING id
            """
            args.append(json.dumps(self.row_data_updates))
        else:
            UPDATE_STATEMENT = """
            UPDATE cdc_events SET is_processed=true,
                                  updated_at=now(),
                                  error_message=$2
            WHERE id=$1
            RETURNING id
            """
        return UPDATE_STATEMENT, args
