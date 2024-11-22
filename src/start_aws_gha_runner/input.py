import json
import os


def _env_parse_helper(
    params: dict, var: str, key: str, is_json: bool = False
) -> dict:
    val = os.environ.get(var)
    if val is not None and val != "":
        if is_json:
            params[key] = json.loads(val)
        else:
            params[key] = val
    return params


def get_var_if_not_empty(var_name, default):
    var = os.environ.get(var_name)
    if var is None or var == "":
        return default
    return var


def parse_aws_params() -> dict:
    params = {}
    ami = os.environ.get("INPUT_AWS_IMAGE_ID")
    if ami is not None:
        params["image_id"] = ami
    instance_type = os.environ.get("INPUT_AWS_INSTANCE_TYPE")
    if instance_type is not None:
        params["instance_type"] = instance_type
    params = _env_parse_helper(params, "INPUT_AWS_SUBNET_ID", "subnet_id")
    params = _env_parse_helper(
        params, "INPUT_AWS_SECURITY_GROUP_ID", "security_group_id"
    )
    params = _env_parse_helper(params, "INPUT_AWS_IAM_ROLE", "iam_role")
    params = _env_parse_helper(params, "INPUT_AWS_TAGS", "tags", is_json=True)
    region_name = os.environ.get("INPUT_AWS_REGION_NAME")
    if region_name is not None:
        params["region_name"] = region_name
    home_dir = os.environ.get("INPUT_AWS_HOME_DIR")
    if home_dir is not None:
        params["home_dir"] = home_dir
    params = _env_parse_helper(params, "INPUT_EXTRA_GH_LABELS", "labels")
    return params
