from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backup_role_is_scoped_to_backup_prefix_and_does_not_decrypt():
    template = (ROOT / "infra/aws-backup-stack.yaml").read_text(encoding="utf-8")
    assert "Resource: !Sub ${BackupBucket.Arn}/jarvis/database/*" in template
    assert "s3:PutObject" in template
    assert "s3:GetObject" in template  # Required by the workflow's head-object verification.
    assert "kms:GenerateDataKey" in template
    assert "kms:Encrypt" in template
    assert "kms:Decrypt" not in template


def test_backup_bucket_enforces_private_versioned_kms_storage():
    template = (ROOT / "infra/aws-backup-stack.yaml").read_text(encoding="utf-8")
    assert "BlockPublicAcls: true" in template
    assert "BlockPublicPolicy: true" in template
    assert "IgnorePublicAcls: true" in template
    assert "RestrictPublicBuckets: true" in template
    assert "Status: Enabled" in template
    assert "SSEAlgorithm: aws:kms" in template
    assert "ExpirationInDays: 30" in template
    assert "NoncurrentDays: 30" in template


def test_github_oidc_trust_is_restricted_to_exact_subject_and_audience():
    template = (ROOT / "infra/aws-backup-stack.yaml").read_text(encoding="utf-8")
    assert "token.actions.githubusercontent.com:aud: sts.amazonaws.com" in template
    assert "token.actions.githubusercontent.com:sub: !Ref GitHubOidcSubject" in template
    assert "repo:tamaszsolt2005-hub@346335800/jarvis-core@1456951119:ref:refs/heads/main" in template
