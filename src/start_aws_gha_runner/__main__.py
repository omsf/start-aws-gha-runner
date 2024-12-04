from start_aws_gha_runner.start import StartAWS
from gha_runner.gh import GitHubInstance
from gha_runner.clouddeployment import DeployInstance
from gha_runner.helper.input import EnvVarBuilder, check_required
import os


def main():
    env = dict(os.environ)
    required = ["GH_PAT", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    # Check that everything exists
    check_required(env, required)
    # The timeout is infallible
    timeout = int(os.environ["INPUT_GH_TIMEOUT"])

    token = os.environ["GH_PAT"]
    # Make a copy of environment variables for immutability
    env = dict(os.environ)
    # instance_count = int(os.environ["INPUT_INSTANCE_COUNT"])

    params = (
        EnvVarBuilder(env)
        .with_var("INPUT_AWS_IMAGE_ID", "image_id")
        .with_var("INPUT_AWS_INSTANCE_TYPE", "instance_type")
        .with_var("INPUT_AWS_SUBNET_ID", "subnet_id")
        .with_var("INPUT_AWS_SECURITY_GROUP_ID", "security_group_id")
        .with_var("INPUT_AWS_IAM_ROLE", "iam_role")
        .with_var("INPUT_AWS_TAGS", "tags", is_json=True)
        .with_var("INPUT_EXTRA_GH_LABELS", "labels")
        .with_var("INPUT_AWS_HOME_DIR", "home_dir")
        .with_var("INPUT_INSTANCE_COUNT", "instance_count", type_hint=int)
        # This is the default case
        .with_var("AWS_REGION", "region_name")
        # This is the input case
        .with_var("INPUT_AWS_REGION_NAME", "region_name")
        # This is the default case
        .with_var("GITHUB_REPOSITORY", "repo")
        # This is the input case
        .with_var("INPUT_GH_REPO", "repo")
        .build()
    )
    repo = params["repo"]
    # This needs to be handled here because the repo is required by the GitHub
    # instance
    if repo is None:
        raise Exception("Repo cannot be empty")

    instance_count = params["instance_count"]

    gh = GitHubInstance(token=token, repo=repo)
    # This will create a new instance of StartAWS and configure it correctly
    deployment = DeployInstance(
        provider_type=StartAWS,
        cloud_params=params,
        gh=gh,
        count=instance_count,
        timeout=timeout,
    )
    # This will output the instance ids for using workflow sytnax
    deployment.start_runner_instances()


if __name__ == "__main__":
    main()
