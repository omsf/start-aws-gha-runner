import re
import pytest
from unittest.mock import patch
from start_aws_gha_runner.__main__ import main

def test_missing_env_vars():
    match = re.escape("Missing required environment variables: ['GH_PAT', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']")
    with patch.dict('os.environ', clear=True):
        with pytest.raises(Exception, match=match):
            main()
