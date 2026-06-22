import pout as pout_module


def test_trigger_requires_auth(client):
    r = client.post('/admin/trigger/pout-post', data={'mode': 'weekday'}, follow_redirects=False)
    assert r.status_code == 302
    assert '/dashboard' not in r.headers['Location']


def test_trigger_pout_post_redirects_to_review(auth_client, monkeypatch):
    monkeypatch.setattr(pout_module, 'generate_post', lambda mode: 42)
    r = auth_client.post('/admin/trigger/pout-post', data={'mode': 'weekday'}, follow_redirects=False)
    assert r.status_code == 302
    assert '/admin/review/42' in r.headers['Location']
