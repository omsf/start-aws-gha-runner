import pytest
from moto import mock_aws
import boto3
from unittest.mock import call, patch, mock_open, Mock
from start_aws_gha_runner.start import StartAWS
from botocore.exceptions import WaiterError, ClientError


@pytest.fixture(scope="function")
def aws():
    with mock_aws():
        params = {
            "image_id": "ami-0772db4c976d21e9b",
            "instance_type": "t2.micro",
            "region_name": "us-east-1",
            "gh_runner_tokens": ["testing"],
            "home_dir": "/home/ec2-user",
            "runner_release": "testing",
            "repo": "omsf-eco-infra/awsinfratesting",
        }
        yield StartAWS(**params)


def test_build_user_data(aws):
    params = {
        "homedir": "/home/ec2-user",
        "script": "echo 'Hello, World!'",
        "repo": "omsf-eco-infra/awsinfratesting",
        "token": "test",
        "labels": "label",
        "runner_release": "test.tar.gz",
    }
    # We strip this to ensure that we don't have any extra whitespace to fail our test
    user_data = aws._build_user_data(**params).strip()
    # We also strip here
    file = """#!/bin/bash
cd "/home/ec2-user"
echo "echo 'Hello, World!'" > pre-runner-script.sh
source pre-runner-script.sh
export RUNNER_ALLOW_RUNASROOT=1
# We will get the latest release from the GitHub API
curl -L test.tar.gz -o runner.tar.gz
tar xzf runner.tar.gz
./config.sh --url https://github.com/omsf-eco-infra/awsinfratesting --token test --labels label --ephemeral
./run.sh
    """.strip()
    assert user_data == file


def test_build_user_data_missing_params(aws):
    params = {
        "homedir": "/home/ec2-user",
        "script": "echo 'Hello, World!'",
        "repo": "omsf-eco-infra/awsinfratesting",
        "token": "test",
    }
    with pytest.raises(Exception):
        aws._build_user_data(**params)

@pytest.fixture(scope="function")
def complete_params():
    params = {
        "image_id": "ami-0772db4c976d21e9b",
        "instance_type": "t2.micro",
        "tags": [
            {"Key": "Name", "Value": "test"},
            {"Key": "Owner", "Value": "test"},
        ],
        "region_name": "us-east-1",
        "gh_runner_tokens": ["testing"],
        "home_dir": "/home/ec2-user",
        "runner_release": "testing",
        "repo": "omsf-eco-infra/awsinfratesting",
        "subnet_id": "test",
        "security_group_id": "test",
        "iam_role": "test",
        "root_device_size": 100
    }
    yield params

def test_build_aws_params(complete_params):
    user_data_params = {
        "token": "test",
        "repo": "omsf-eco-infra/awsinfratesting",
        "homedir": "/home/ec2-user",
        "script": "echo 'Hello, World!'",
        "runner_release": "test.tar.gz",
        "labels": "label",
    }
    aws = StartAWS(**complete_params)
    params = aws._build_aws_params(user_data_params)
    assert params == {
        "ImageId": "ami-0772db4c976d21e9b",
        "InstanceType": "t2.micro",
        "MinCount": 1,
        "MaxCount": 1,
        "SubnetId": "test",
        "SecurityGroupIds": ["test"],
        "IamInstanceProfile": {"Name": "test"},
        "UserData": """#!/bin/bash
cd "/home/ec2-user"
echo "echo 'Hello, World!'" > pre-runner-script.sh
source pre-runner-script.sh
export RUNNER_ALLOW_RUNASROOT=1
# We will get the latest release from the GitHub API
curl -L test.tar.gz -o runner.tar.gz
tar xzf runner.tar.gz
./config.sh --url https://github.com/omsf-eco-infra/awsinfratesting --token test --labels label --ephemeral
./run.sh
""",
        "TagSpecifications": [
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": "test"},
                    {"Key": "Owner", "Value": "test"},
                ],
            }
        ],
    }

def test_modify_root_disk_size(complete_params):
    mock_client = Mock()

    # Mock image data with all device mappings
    mock_image_data = {
        "Images": [{
            "RootDeviceName": "/dev/sda1",
            "BlockDeviceMappings": [
                {
                    "Ebs": {
                        "DeleteOnTermination": True,
                        "VolumeSize": 50,
                        "VolumeType": "gp3",
                        "Encrypted": False
                    },
                    "DeviceName": "/dev/sda1"
                },
                {
                    "DeviceName": "/dev/sdb",
                    "VirtualName": "ephemeral0"
                },
                {
                    "DeviceName": "/dev/sdc",
                    "VirtualName": "ephemeral1"
                }
            ]
        }]
    }

    def mock_describe_images(**kwargs):
        if kwargs.get('DryRun', False):
            raise ClientError(
                error_response={"Error": {"Code": "DryRunOperation"}},
                operation_name="DescribeImages"
            )
        return mock_image_data

    mock_client.describe_images = mock_describe_images
    aws = StartAWS(**complete_params)
    out = aws._modify_root_disk_size(mock_client, {})
    # Expected output should preserve all devices, only modifying root volume size
    expected_output = {
        "BlockDeviceMappings": [
            {
                "DeviceName": "/dev/sda1",
                "Ebs": {
                    "DeleteOnTermination": True,
                    "VolumeSize": 100,
                    "VolumeType": "gp3",
                    "Encrypted": False
                }
            },
            {
                "DeviceName": "/dev/sdb",
                "VirtualName": "ephemeral0"
            },
            {
                "DeviceName": "/dev/sdc",
                "VirtualName": "ephemeral1"
            }
        ]
    }
    assert out == expected_output

def test_modify_root_disk_size_permission_error(complete_params):
    mock_client = Mock()

    # Mock permission denied error
    mock_client.describe_images.side_effect = ClientError(
        error_response={'Error': {'Code': 'AccessDenied'}},
        operation_name='DescribeImages'
    )

    aws = StartAWS(**complete_params)

    with pytest.raises(ClientError) as exc_info:
        aws._modify_root_disk_size(mock_client, {})

    assert 'AccessDenied' in str(exc_info.value)

def test_modify_root_disk_size_no_change(complete_params):
    mock_client = Mock()
    complete_params["root_device_size"] = 0

    mock_image_data = {
        "Images": [{
            "RootDeviceName": "/dev/sda1",
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "VolumeSize": 50,
                        "VolumeType": "gp3"
                    }
                },
                {
                    "DeviceName": "/dev/sdb",
                    "VirtualName": "ephemeral0"
                }
            ]
        }]
    }

    def mock_describe_images(**kwargs):
        if kwargs.get('DryRun', False):
            raise ClientError(
                error_response={'Error': {'Code': 'DryRunOperation'}},
                operation_name='DescribeImages'
            )
        return mock_image_data

    mock_client.describe_images = mock_describe_images

    aws = StartAWS(**complete_params)
    input_params = {}
    result = aws._modify_root_disk_size(mock_client, input_params)

    # With root_device_size = 0, no modifications should be made
    assert result == input_params

def test_create_instance_with_labels(aws):
    aws.labels = "test"
    ids = aws.create_instances()
    assert len(ids) == 1


def test_create_instances(aws):
    ids = aws.create_instances()
    assert len(ids) == 1


def test_create_instances_missing_release(aws):
    aws.runner_release = ""
    with pytest.raises(
        ValueError, match="No runner release provided, cannot create instances."
    ):
        aws.create_instances()


def test_create_instances_missing_home_dir(aws):
    aws.home_dir = ""
    with pytest.raises(
        ValueError, match="No home directory provided, cannot create instances."
    ):
        aws.create_instances()


def test_create_instances_missing_tokens(aws):
    aws.gh_runner_tokens = []
    with pytest.raises(
        ValueError,
        match="No GitHub runner tokens provided, cannot create instances.",
    ):
        aws.create_instances()


def test_create_instances_missing_image_id(aws):
    aws.image_id = ""
    with pytest.raises(
        ValueError, match="No image ID provided, cannot create instances."
    ):
        aws.create_instances()


def test_create_instances_missing_instance_type(aws):
    aws.instance_type = ""
    with pytest.raises(
        ValueError, match="No instance type provided, cannot create instances."
    ):
        aws.create_instances()


def test_create_instances_missing_region_name(aws):
    aws.region_name = ""
    with pytest.raises(
        ValueError, match="No region name provided, cannot create instances."
    ):
        aws.create_instances()


def test_wait_until_ready(aws):
    ids = aws.create_instances()
    params = {
        "MaxAttempts": 1,
        "Delay": 5,
    }
    ids = list(ids)
    aws.wait_until_ready(ids, **params)


def test_wait_until_ready_dne(aws):
    # This is a fake instance id
    ids = ["i-xxxxxxxxxxxxxxxxx"]
    params = {
        "MaxAttempts": 1,
        "Delay": 5,
    }
    with pytest.raises(WaiterError):
        aws.wait_until_ready(ids, **params)


@pytest.mark.slow
def test_wait_until_ready_dne_long(aws):
    # This is a fake instance id
    ids = ["i-xxxxxxxxxxxxxxxxx"]
    # Runs with the default parameters
    with pytest.raises(WaiterError):
        aws.wait_until_ready(ids)


def test_set_instance_mapping(aws, monkeypatch):
    monkeypatch.setenv("GITHUB_OUTPUT", "mock_output_file")
    mapping = {"i-xxxxxxxxxxxxxxxxx": "test"}
    mock_file = mock_open()

    with patch("builtins.open", mock_file):
        aws.set_instance_mapping(mapping)

    assert mock_file.call_args_list == [
        call("mock_output_file", "a"),
        call("mock_output_file", "a"),
    ]
