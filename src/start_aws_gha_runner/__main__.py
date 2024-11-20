from start_aws_gha_runner.input import parse_aws_params
from start_aws_gha_runner.start import StartAWS
from gha_runner.gh import GitHubInstance
from gha_runner.clouddeployment import DeployInstance
import os


def main():
    required = ["GH_PAT", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    for req in required:
        if req not in os.environ:
            raise Exception(f"Missing required environment variable {req}")

    # Set the default timeout to 20 minutes
    timeout = os.environ.get("INPUT_GH_TIMEOUT")
    gh_timeout = 1200
    if timeout is not None and timeout != "":
        gh_timeout = int(timeout)

    gha_params = {
        "token": os.environ["GH_PAT"],
    }
    repo = os.environ.get("INPUT_REPO")
    if repo is None or repo == "":
        repo = os.environ.get("GITHUB_REPOSITORY")
    # We check again to validate that this was set correctly
    if repo is not None or repo == "":
        gha_params["repo"] = repo
    else:
        raise Exception("Repo key is missing or GITHUB_REPOSITORY is missing")
    instance_count = int(os.environ["INPUT_INSTANCE_COUNT"])

    aws_params = parse_aws_params()
    aws_params["repo"] = gha_params["repo"]
    gh = GitHubInstance(token=os.environ["GH_PAT"], repo=gha_params["repo"])
    # This will create a new instance of StartAWS and configure it correctly
    deployment = DeployInstance(
        provider_type=StartAWS,
        cloud_params=aws_params,
        gh=gh,
        count=instance_count,
        timeout=gh_timeout,
    )
    # This will output the instance ids for using workflow sytnax
    deployment.start_runner_instances()


if __name__ == "__main__":
    main()
