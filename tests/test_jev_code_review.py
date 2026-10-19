"""Review answers are advisory; reject malformed contracts, tolerate decimal rounding."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review_bb3_code_with_jev import validate


def test_custom_review_scope_rejected_before_network_if_oversized(tmp_path):
    from review_bb3_code_with_jev import main
    source = tmp_path / 'candidate.py'
    checks = tmp_path / 'checks.py'
    source.write_text('x = 1\n', encoding='utf-8')
    checks.write_text('#' + 'x' * 28000, encoding='utf-8')
    with pytest.raises(ValueError, match='context too large'):
        main(source, checks, {'causality':'Only known bars',
                             'selection':'No optimization', 'separation':'No AI trades'})


def test_rounded_probabilities_and_contradictions():
    r = {'model':'jev-1.13.0','usage':{'input_tokens':123},'answers':{
        k:{'type':'choice','choice':'supports','confidence':.72,
           'probabilities':{'supports':.81,'contradicts':.13,'insufficient':.05}}
        for k in ('causality','selection','separation')}}
    validate(r)
    r['answers']['causality']['choice']='contradicts'
    with pytest.raises(ValueError):
        validate(r)
    r['answers']['causality']['probabilities']['supports']=float('nan')
    with pytest.raises(ValueError):
        validate(r)
