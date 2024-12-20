# start_aws_gha_runner
This repository contains the code to start a GitHub Actions runner on an AWS EC2 instance.
## Inputs
| Input                 | Description                                                                                                        | Required for start | Default |
|-----------------------|--------------------------------------------------------------------------------------------------------------------|------------------- |---------|
| aws_home_dir          | The AWS AMI home directory to use for your runner. Will not start if not specified.                                | true               |         |
| aws_iam_role          | The optional AWS IAM role to assume for provisioning your runner.                                                  | false              |         |
| aws_image_id          | The machine AMI to use for your runner. This AMI can be a default but should have docker installed in the AMI.     | true               |         |
| aws_instance_type     | The type of instance to use for your runner. For example: t2.micro, t4g.nano, etc. Will not start if not specified.| true               |         |
| aws_region_name       | The AWS region name to use for your runner. Defaults to AWS_REGION                                                 | true               |         |
| aws_security_group_id | The AWS security group ID to use for your runner. Will use the account default security group if not specified.    | false              | The default AWS security group |
| aws_subnet_id         | The AWS subnet ID to use for your runner. Will use the account default subnet if not specified.                    | false              | The default AWS subnet ID |
| aws_tags              | The AWS tags to use for your runner, formatted as a JSON list. See `README` for more details.                      | false              |         |
| extra_gh_labels       | Any extra GitHub labels to tag your runners with. Passed as a comma-separated list with no spaces.                 | false              |         |
| instance_count        | The number of instances to create, defaults to 1                                                                   | false              | 1       |
| repo     | The repo to run against. Will use the current repo if not specified.       | false    | The repo the runner is running in |
| gh_timeout            | The timeout in seconds to wait for the runner to come online as seen by the GitHub API. Defaults to 1200 seconds.  | false              | 1200    |
## Outputs
| Name | Description |
| ---- | ----------- |
| mapping | A JSON object mapping instance IDs to unique GitHub runner labels. This is used in conjunction with the `instance_mapping` input when stopping. |
| instances | A JSON list of the GitHub runner labels to be used in the 'runs-on' field |
## Example usage
```yaml
name: Start AWS GHA Runner
on:
  workflow_run:
jobs:
  start-aws-runner:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    outputs:
      mapping: ${{ steps.aws-start.outputs.mapping }}
      instances: ${{ steps.aws-start.outputs.instances }}
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE }}
          aws-region: us-east-1
      - name: Create cloud runner
        id: aws-start
        uses: omsf-eco-infra/start-aws-gha-runner@v1.0.0
        with:
          aws_image_id: ami-0f7c4a792e3fb63c8
          aws_instance_type: g4dn.xlarge
          aws_home_dir: /home/ubuntu
        env:
          GH_PAT: ${{ secrets.GH_PAT }}
```
