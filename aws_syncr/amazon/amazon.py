from aws_syncr.errors import BadCredentials, AwsSyncrError

from botocore.exceptions import ClientError
import boto3

from contextlib import contextmanager
import logging

log = logging.getLogger("aws_syncr.amazon.amazon")

class Amazon(object):
    def __init__(self, environment, accounts, debug=False):
        self.debug = debug
        self.accounts = accounts
        self.environment = environment

    @property
    def all_roles(self):
        if not hasattr(self, "_all_roles"):
            self.validate_account()
        return self._all_roles

    @property
    def all_users(self):
        if not hasattr(self, "_all_users"):
            self.validate_account()
        return self._all_users

    def validate_account(self):
        """Make sure we are able to connect to the right account"""
        with self.catch_invalid_credentials():
            log.info("Finding a role to check the account id")
            all_roles = self._all_roles = list(boto3.resource('iam').roles.all())
            if not all_roles:
                raise AwsSyncrError("Couldn't find an iam role, can't validate the account....")
            account_id = all_roles[0].meta.data['Arn'].split(":", 5)[4]

        chosen_account = self.accounts[self.environment]
        if chosen_account != account_id:
            raise BadCredentials("Don't have credentials for the correct account!", wanted=chosen_account, got=account_id)

        with self.catch_invalid_credentials():
            log.info("Finding users in your account")
            self._all_users = list(boto3.resource('iam').users.all())

    @contextmanager
    def catch_invalid_credentials(self):
        try:
            yield
        except ClientError as error:
            if error.response["ResponseMetadata"]["HTTPStatsuCode"] == 403:
                raise BadCredentials("Failed to find valid credentials", error=error.message)
            else:
                raise
