import copy
import hashlib
import json

import pytest

from etudecas.reference_status import digest, verify_reference, documentation_coverage


def test_reference_check_detects_changes_without_accepting_them(tmp_path):
    path=tmp_path/'data.csv'
    path.write_text('original')
    manifest={'schema_version':'etudecas.fixed_reference.v1','reference_id':'test',
              'files':[{'path':'data.csv','role':'nominal','sha256':digest(path)}]}
    saved=copy.deepcopy(manifest)
    assert verify_reference(tmp_path,manifest)['ok']
    path.write_text('modified')
    assert verify_reference(tmp_path,manifest)['counts']=={'changed':1}
    path.unlink()
    assert verify_reference(tmp_path,manifest)['counts']=={'missing':1}
    assert manifest==saved


@pytest.mark.parametrize('path',['../outside','C:/outside','/outside','a/../../outside'])
def test_reference_rejects_paths_outside_workspace(tmp_path,path):
    manifest={'schema_version':'etudecas.fixed_reference.v1','reference_id':'test',
              'files':[{'path':path,'role':'nominal','sha256':'0'*64}]}
    with pytest.raises(ValueError): verify_reference(tmp_path,manifest)


def test_empty_reference_cannot_pass(tmp_path):
    with pytest.raises(ValueError):
        verify_reference(tmp_path,{'schema_version':'etudecas.fixed_reference.v1','files':[]})


def test_documentary_hash_uses_builder_normalization_and_detects_content_changes(tmp_path):
    docs=tmp_path/'etudecas/docs'
    docs.mkdir(parents=True)
    (docs/'catalog.json').write_text(json.dumps({'registries':[{'registry':'registry.json'}]}))
    (tmp_path/'business.md').write_bytes(b'\xef\xbb\xbfBusiness\r\n')
    (tmp_path/'registry.json').write_text(json.dumps({'title':'Test','references':[],
        'rules':[{'status':'documented'}],
        'business_source_fingerprints':{'business.md':hashlib.sha256(b'Business\n').hexdigest()}}))
    assert not documentation_coverage(tmp_path)['review_needed']
    (tmp_path/'business.md').write_text('Changed\n')
    assert documentation_coverage(tmp_path)['review_needed']
