import boto3
import pytest
from moto import mock_aws
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


@pytest.fixture(scope="function")
def aws_latest_ami():
    with mock_aws():
        params = {
            "image_id": "latest",
            # This comes from https://github.com/getmoto/moto/blob/master/moto/ec2/resources/amis.json
            # These are AMIs used to mock out data.
            # For more info see here:
            # https://docs.getmoto.org/en/latest/docs/services/ec2.html
            "image_name": "Ubuntu CUDA9 DLAMI",
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
    # Strip to ensure extra whitespace does not fail the test.
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
./config.sh --url https://github.com/omsf-eco-infra/awsinfratesting \
--token test --labels label --ephemeral
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
        "root_device_size": 100,
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
./config.sh --url https://github.com/omsf-eco-infra/awsinfratesting \
--token test --labels label --ephemeral
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


@pytest.mark.parametrize(
    "market_overrides, expected_market_options",
    [
        pytest.param(
            {"market_type": "spot", "spot_max_price": "0.50"},
            {"MarketType": "spot", "SpotOptions": {"MaxPrice": "0.50"}},
            id="spot-with-max-price",
        ),
        pytest.param(
            {"market_type": "spot"},
            {"MarketType": "spot"},
            id="spot-no-max-price",
        ),
        pytest.param(
            {},
            None,
            id="on-demand-default",
        ),
    ],
)
def test_build_aws_params_market_options(
    complete_params, market_overrides, expected_market_options
):
    user_data_params = {
        "token": "test",
        "repo": "omsf-eco-infra/awsinfratesting",
        "homedir": "/home/ec2-user",
        "script": "echo 'Hello, World!'",
        "runner_release": "test.tar.gz",
        "labels": "label",
    }
    complete_params.update(market_overrides)
    aws = StartAWS(**complete_params)
    params = aws._build_aws_params(user_data_params)
    if expected_market_options is None:
        assert "InstanceMarketOptions" not in params
    else:
        assert params["InstanceMarketOptions"] == expected_market_options


def test_modify_root_disk_size(complete_params):
    mock_client = Mock()

    # Mock image data with all device mappings
    mock_image_data = {
        "Images": [
            {
                "RootDeviceName": "/dev/sda1",
                "BlockDeviceMappings": [
                    {
                        "Ebs": {
                            "DeleteOnTermination": True,
                            "VolumeSize": 50,
                            "VolumeType": "gp3",
                            "Encrypted": False,
                        },
                        "DeviceName": "/dev/sda1",
                    },
                    {"DeviceName": "/dev/sdb", "VirtualName": "ephemeral0"},
                    {"DeviceName": "/dev/sdc", "VirtualName": "ephemeral1"},
                ],
            }
        ]
    }

    def mock_describe_images(**kwargs):
        if kwargs.get("DryRun", False):
            raise ClientError(
                error_response={"Error": {"Code": "DryRunOperation"}},
                operation_name="DescribeImages",
            )
        return mock_image_data

    mock_client.describe_images = mock_describe_images
    aws = StartAWS(**complete_params)
    out = aws._modify_root_disk_size(mock_client, {})
    # Preserve all devices, modifying only the root volume size.
    expected_output = {
        "BlockDeviceMappings": [
            {
                "DeviceName": "/dev/sda1",
                "Ebs": {
                    "DeleteOnTermination": True,
                    "VolumeSize": 100,
                    "VolumeType": "gp3",
                    "Encrypted": False,
                },
            },
            {"DeviceName": "/dev/sdb", "VirtualName": "ephemeral0"},
            {"DeviceName": "/dev/sdc", "VirtualName": "ephemeral1"},
        ]
    }
    assert out == expected_output


def test_modify_root_disk_size_permission_error(complete_params):
    mock_client = Mock()

    # Mock permission denied error
    mock_client.describe_images.side_effect = ClientError(
        error_response={"Error": {"Code": "AccessDenied"}},
        operation_name="DescribeImages",
    )

    aws = StartAWS(**complete_params)

    with pytest.raises(ClientError) as exc_info:
        aws._modify_root_disk_size(mock_client, {})

    assert "AccessDenied" in str(exc_info.value)


def test_modify_root_disk_size_no_change(complete_params):
    mock_client = Mock()
    complete_params["root_device_size"] = 0

    mock_image_data = {
        "Images": [
            {
                "RootDeviceName": "/dev/sda1",
                "BlockDeviceMappings": [
                    {
                        "DeviceName": "/dev/sda1",
                        "Ebs": {"VolumeSize": 50, "VolumeType": "gp3"},
                    },
                    {"DeviceName": "/dev/sdb", "VirtualName": "ephemeral0"},
                ],
            }
        ]
    }

    def mock_describe_images(**kwargs):
        if kwargs.get("DryRun", False):
            raise ClientError(
                error_response={"Error": {"Code": "DryRunOperation"}},
                operation_name="DescribeImages",
            )
        return mock_image_data

    mock_client.describe_images = mock_describe_images

    aws = StartAWS(**complete_params)
    input_params = {}
    result = aws._modify_root_disk_size(mock_client, input_params)

    # With root_device_size = 0, no modifications should be made
    assert result == input_params


@pytest.fixture(scope="function")
def complete_params_latest():
    params = {
        "image_name": (
            "Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)"
        ),
        "image_id": "latest",
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
        "root_device_size": 100,
    }
    yield params


def test_fetch_latest_ami(complete_params_latest):
    mock_client = Mock()

    mock_image_data = {
        "Images": [
            {"CreationDate": "2025-08-03", "ImageId": "ami-12345678"},
            {"CreationDate": "2025-08-05", "ImageId": "ami-89123456"},
            {"CreationDate": "2025-09-05", "ImageId": "ami-89121111"},
        ]
    }
    mock_client.describe_images.return_value = mock_image_data
    aws = StartAWS(**complete_params_latest)
    result = aws._fetch_latest_ami(mock_client, "Test")
    assert result == "ami-89121111"


def test_create_instances_latest(aws_latest_ami):
    ids = aws_latest_ami.create_instances()
    assert len(ids) == 1


def test_create_instatnces_latest_no_name(aws_latest_ami):
    aws_latest_ami.image_name = ""
    with pytest.raises(
        ValueError, match="Looking for latest image but name not provided"
    ):
        aws_latest_ami.create_instances()


def test_create_instance_with_labels(aws):
    aws.labels = "test"
    ids = aws.create_instances()
    assert len(ids) == 1


def test_create_instances(aws):
    ids = aws.create_instances()
    assert len(ids) == 1


def capacity_error(code="InsufficientInstanceCapacity"):
    return ClientError(
        error_response={"Error": {"Code": code}},
        operation_name="RunInstances",
    )


def mock_zones(*names):
    return {"AvailabilityZones": [{"ZoneName": name} for name in names]}


@pytest.mark.parametrize(
    "error_code",
    [
        "InsufficientHostCapacity",
        "InsufficientInstanceCapacity",
        "Unsupported",
    ],
)
def test_create_instances_falls_back_across_availability_zones(aws, error_code):
    client = Mock()
    client.describe_availability_zones.return_value = mock_zones(
        "us-east-1c", "us-east-1a", "us-east-1b"
    )
    client.run_instances.side_effect = [
        capacity_error(error_code),
        {"Instances": [{"InstanceId": "i-second-zone"}]},
    ]

    with patch("start_aws_gha_runner.start.boto3.client", return_value=client):
        ids = aws.create_instances()

    assert list(ids) == ["i-second-zone"]
    assert [
        attempt.kwargs["Placement"]["AvailabilityZone"]
        for attempt in client.run_instances.call_args_list
    ] == ["us-east-1a", "us-east-1b"]


def test_run_instances_requires_an_available_zone(aws):
    client = Mock()

    with pytest.raises(
        ValueError, match="No available Availability Zones found"
    ):
        aws._run_instances_with_fallback(client, {}, [], 0)

    client.run_instances.assert_not_called()


def test_create_instances_raises_after_all_zones_fail(aws):
    client = Mock()
    client.describe_availability_zones.return_value = mock_zones(
        "us-east-1a", "us-east-1b"
    )
    client.run_instances.side_effect = [capacity_error(), capacity_error()]

    with patch("start_aws_gha_runner.start.boto3.client", return_value=client):
        with pytest.raises(ClientError, match="InsufficientInstanceCapacity"):
            aws.create_instances()

    assert client.run_instances.call_count == 2


def test_create_instances_distributes_initial_attempts_across_zones(aws):
    client = boto3.client("ec2", region_name=aws.region_name)
    zones = aws._available_zones(client)
    aws.gh_runner_tokens = ["token"] * (len(zones) + 1)

    ids = aws.create_instances()

    placements = [
        client.describe_instances(InstanceIds=[instance_id])["Reservations"][0][
            "Instances"
        ][0]["Placement"]["AvailabilityZone"]
        for instance_id in ids
    ]
    assert placements == zones + zones[:1]


def test_create_instances_does_not_retry_non_capacity_errors(aws):
    client = Mock()
    client.describe_availability_zones.return_value = mock_zones(
        "us-east-1a", "us-east-1b"
    )
    client.run_instances.side_effect = capacity_error("UnauthorizedOperation")

    with patch("start_aws_gha_runner.start.boto3.client", return_value=client):
        with pytest.raises(ClientError, match="UnauthorizedOperation"):
            aws.create_instances()

    client.run_instances.assert_called_once()


def test_create_instances_with_subnet_does_not_select_zone(aws):
    aws.subnet_id = "subnet-123"
    client = Mock()
    client.run_instances.return_value = {
        "Instances": [{"InstanceId": "i-subnet"}]
    }

    with patch("start_aws_gha_runner.start.boto3.client", return_value=client):
        aws.create_instances()

    client.describe_availability_zones.assert_not_called()
    assert client.run_instances.call_args.kwargs["SubnetId"] == "subnet-123"
    assert "Placement" not in client.run_instances.call_args.kwargs


def test_create_instances_raises_when_api_has_no_available_zone(aws):
    client = Mock()
    client.describe_availability_zones.return_value = mock_zones()

    with patch("start_aws_gha_runner.start.boto3.client", return_value=client):
        with pytest.raises(ValueError, match="No available Availability Zones"):
            aws.create_instances()

    client.run_instances.assert_not_called()


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
