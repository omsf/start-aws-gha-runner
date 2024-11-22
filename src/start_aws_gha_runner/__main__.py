from start_aws_gha_runner.input import parse_aws_params
from start_aws_gha_runner.start import StartAWS
from gha_runner.gh import GitHubInstance
from gha_runner.clouddeployment import DeployInstance
import os


def check_required_env_vars():
    required = ["GH_PAT", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    for req in required:
        if req not in os.environ:
            raise Exception(f"Missing required environment variable {req}")

def main():
    # Check that everything exists
    check_required_env_vars()
    # The timeout is infallible
    timeout = int(os.environ["INPUT_GH_TIMEOUT"])
    # timeout = os.environ.get("INPUT_GH_TIMEOUT")
    # gh_timeout = 1200
    # if timeout is not None and timeout != "":
    #     gh_timeout = int(timeout)

    token = os.environ["GH_PAT"]
    # If the repo is not set, use the calling repo
    calling_repo = os.environ["GITHUB_REPOSITORY"]
    repo = os.environ.get("INPUT_REPO", calling_repo)

    # This is infallable because it has a default value
    instance_count = int(os.environ["INPUT_INSTANCE_COUNT"])

    aws_params = parse_aws_params()
    aws_params["repo"] = repo
    gh = GitHubInstance(token=token, repo=repo)
    # This will create a new instance of StartAWS and configure it correctly
    deployment = DeployInstance(
        provider_type=StartAWS,
        cloud_params=aws_params,
        gh=gh,
        count=instance_count,
        timeout=timeout,
    )
    # This will output the instance ids for using workflow sytnax
    deployment.start_runner_instances()


if __name__ == "__main__":
    main()
