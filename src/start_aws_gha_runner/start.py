import importlib.resources
from dataclasses import dataclass, field
from string import Template

import boto3
from gha_runner import gh
from gha_runner.clouddeployment import CreateCloudInstance


@dataclass
class StartAWS(CreateCloudInstance):
    image_id: str
    instance_type: str
    home_dir: str
    repo: str
    region_name: str
    runner_release: str = ""
    tags: list[dict[str, str]] = field(default_factory=list)
    gh_runner_tokens: list[str] = field(default_factory=list)
    labels: str = ""
    subnet_id: str = ""
    security_group_id: str = ""
    iam_role: str = ""
    script: str = ""

    def _build_aws_params(self, user_data_params: dict) -> dict:
        """Build the parameters for the AWS API call.

        Parameters
        ----------
        count : int
            The number of instances to create.
        user_data_params : dict
            A dictionary of parameters to pass to the user

        Returns
        -------
        dict
            A dictionary of parameters for the AWS API call.

        """
        params = {
            "ImageId": self.image_id,
            "InstanceType": self.instance_type,
            "MinCount": 1,
            "MaxCount": 1,
            "UserData": self._build_user_data(**user_data_params),
        }
        if self.subnet_id != "":
            params["SubnetId"] = self.subnet_id
        if self.security_group_id != "":
            params["SecurityGroupIds"] = [self.security_group_id]
        if self.iam_role != "":
            params["IamInstanceProfile"] = {"Name": self.iam_role}
        if len(self.tags) > 0:
            specs = {"ResourceType": "instance", "Tags": self.tags}
            params["TagSpecifications"] = [specs]

        return params

    def _build_user_data(self, **kwargs) -> str:
        """Build the user data script.

        Parameters
        ----------
        kwargs : dict
            A dictionary of parameters to pass to the template.

        Returns
        -------
        str
            The user data script as a string.

        """
        template = importlib.resources.files("gha_runner").joinpath(
            "templates/user-script.sh.templ"
        )
        with template.open() as f:
            template = f.read()
            try:
                parsed = Template(template)
                return parsed.substitute(**kwargs)
            except Exception as e:
                raise Exception(f"Error parsing user data template: {e}")

    def create_instances(self) -> dict[str, str]:
        if not self.gh_runner_tokens:
            raise ValueError(
                "No GitHub runner tokens provided, cannot create instances."
            )
        if not self.runner_release:
            raise ValueError(
                "No runner release provided, cannot create instances."
            )
        if not self.home_dir:
            raise ValueError(
                "No home directory provided, cannot create instances."
            )
        if not self.image_id:
            raise ValueError("No image ID provided, cannot create instances.")
        if not self.instance_type:
            raise ValueError(
                "No instance type provided, cannot create instances."
            )
        ec2 = boto3.client("ec2", region_name=self.region_name)
        id_dict = {}
        for token in self.gh_runner_tokens:
            label = gh.GitHubInstance.generate_random_label()
            labels = self.labels
            if labels == "":
                labels = label
            else:
                labels = self.labels + "," + label
            user_data_params = {
                "token": token,
                "repo": self.repo,
                "homedir": self.home_dir,
                "script": self.script,
                "runner_release": self.runner_release,
                "labels": labels,
            }
            params = self._build_aws_params(user_data_params)
            result = ec2.run_instances(**params)
            instances = result["Instances"]
            id = instances[0]["InstanceId"]
            id_dict[id] = label
        return id_dict

    def wait_until_ready(self, ids: list[str], **kwargs):
        ec2 = boto3.client("ec2", self.region_name)
        waiter = ec2.get_waiter("instance_running")
        # Pass custom config for the waiter
        if kwargs:
            waiter.wait(InstanceIds=ids, WaiterConfig=kwargs)
        # Otherwise, use the default config
        else:
            waiter.wait(InstanceIds=ids)
