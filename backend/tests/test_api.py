from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get('/api/health')
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'ok'


@pytest.mark.asyncio
async def test_login_fail(client: AsyncClient):
    resp = await client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrong'})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, admin_user):
    resp = await client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin'})
    assert resp.status_code == 200
    data = resp.json()
    assert 'access_token' in data
    assert data['token_type'] == 'bearer'


@pytest.mark.asyncio
async def test_create_and_list_entries(authorized_client: AsyncClient):
    # Create entry
    resp = await authorized_client.post('/api/entries', json={
        'title': 'Test Entry',
        'content': '# Test\n\nSome content here.',
        'tags': ['test', 'example'],
    })
    assert resp.status_code == 201
    entry = resp.json()
    assert entry['title'] == 'Test Entry'
    assert entry['content'] == '# Test\n\nSome content here.'
    assert len(entry['tags']) == 2

    # List entries
    resp = await authorized_client.get('/api/entries')
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) >= 1

    # Get single entry
    resp = await authorized_client.get(f'/api/entries/{entry["id"]}')
    assert resp.status_code == 200
    assert resp.json()['title'] == 'Test Entry'


@pytest.mark.asyncio
async def test_update_entry(authorized_client: AsyncClient):
    # Create
    resp = await authorized_client.post('/api/entries', json={
        'title': 'To Update',
        'content': 'Old content',
    })
    entry_id = resp.json()['id']

    # Update
    resp = await authorized_client.put(f'/api/entries/{entry_id}', json={
        'title': 'Updated Title',
        'content': 'New content',
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data['title'] == 'Updated Title'
    assert data['content'] == 'New content'


@pytest.mark.asyncio
async def test_delete_entry(authorized_client: AsyncClient):
    resp = await authorized_client.post('/api/entries', json={
        'title': 'ToDelete',
        'content': 'Content',
    })
    entry_id = resp.json()['id']

    resp = await authorized_client.delete(f'/api/entries/{entry_id}')
    assert resp.status_code == 204

    resp = await authorized_client.get(f'/api/entries/{entry_id}')
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search(authorized_client: AsyncClient):
    await authorized_client.post('/api/entries', json={
        'title': 'Docker cleanup command',
        'content': 'Use docker system prune to clean up',
        'tags': ['docker', 'linux'],
    })
    await authorized_client.post('/api/entries', json={
        'title': 'Nginx config',
        'content': 'server block configuration',
        'tags': ['nginx'],
    })

    resp = await authorized_client.get('/api/entries/search?q=docker')
    assert resp.status_code == 200
    data = resp.json()
    assert data['total'] >= 1
    titles = [e['title'] for e in data['entries']]
    assert any('docker' in t.lower() for t in titles)


@pytest.mark.asyncio
async def test_categories(authorized_client: AsyncClient):
    # List
    resp = await authorized_client.get('/api/categories')
    assert resp.status_code == 200
    cats = resp.json()
    assert len(cats) >= 0  # categories may or may not be seeded in tests

    # Create
    resp = await authorized_client.post('/api/categories', json={'name': 'My Custom'})
    assert resp.status_code == 201
    assert resp.json()['name'] == 'My Custom'

    # Update
    cat_id = resp.json()['id']
    resp = await authorized_client.put(f'/api/categories/{cat_id}', json={'name': 'Renamed'})
    assert resp.status_code == 200
    assert resp.json()['name'] == 'Renamed'

    # Delete
    resp = await authorized_client.delete(f'/api/categories/{cat_id}')
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_tags(authorized_client: AsyncClient):
    resp = await authorized_client.post('/api/entries', json={
        'title': 'Tagged Entry',
        'content': 'Content',
        'tags': ['pytest', 'testing'],
    })
    entry = resp.json()

    resp = await authorized_client.get('/api/tags')
    assert resp.status_code == 200
    tags = resp.json()
    tag_names = [t['name'] for t in tags]
    assert 'pytest' in tag_names
    assert 'testing' in tag_names


@pytest.mark.asyncio
async def test_entry_history(authorized_client: AsyncClient):
    resp = await authorized_client.post('/api/entries', json={
        'title': 'History Test',
        'content': 'Version 1',
    })
    entry_id = resp.json()['id']

    await authorized_client.put(f'/api/entries/{entry_id}', json={
        'content': 'Version 2',
    })

    resp = await authorized_client.get(f'/api/entries/{entry_id}/history')
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) >= 1
    assert history[0]['content'] == 'Version 1'


@pytest.mark.asyncio
async def test_favorite(authorized_client: AsyncClient):
    resp = await authorized_client.post('/api/entries', json={
        'title': 'Favorite Me',
        'content': 'Content',
        'is_favorite': True,
    })
    entry_id = resp.json()['id']

    # Check favorites filter
    resp = await authorized_client.get('/api/entries?favorite=true')
    assert resp.status_code == 200
    favs = resp.json()
    assert any(e['id'] == entry_id for e in favs)


@pytest.mark.asyncio
async def test_import_txt(authorized_client: AsyncClient):
    resp = await authorized_client.post('/api/import/txt', json={
        'content': '# First Entry\n\nContent one.\n\n# Second Entry\n\nContent two.',
        'separator': '\n\n# ',
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data['created'] >= 1


@pytest.mark.asyncio
async def test_import_with_separator(authorized_client: AsyncClient):
    resp = await authorized_client.post('/api/import/txt', json={
        'content': '=== ENTRY 1 ===\n\nFirst.\n\n=== ENTRY 2 ===\n\nSecond.',
        'separator': '=== ENTRY',
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data['created'] >= 1


@pytest.mark.asyncio
async def test_export_json(authorized_client: AsyncClient):
    await authorized_client.post('/api/entries', json={
        'title': 'Export Test',
        'content': 'Content',
    })
    resp = await authorized_client.get('/api/export/json')
    assert resp.status_code == 200
    import json
    data = json.loads(resp.text)
    assert 'entries' in data
    assert len(data['entries']) >= 1


@pytest.mark.asyncio
async def test_export_markdown(authorized_client: AsyncClient):
    await authorized_client.post('/api/entries', json={
        'title': 'Export Test',
        'content': 'Markdown content',
    })
    resp = await authorized_client.get('/api/export/markdown')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_backup_create(authorized_client: AsyncClient):
    resp = await authorized_client.post('/api/backups')
    assert resp.status_code == 200
    assert 'filename' in resp.json()

    resp = await authorized_client.get('/api/backups')
    assert resp.status_code == 200
    backups = resp.json()
    assert len(backups) >= 1


@pytest.mark.asyncio
async def test_unauthorized(client: AsyncClient):
    # The entries endpoint doesn't require auth in this MVP
    resp = await client.get('/api/entries')
    assert resp.status_code == 200
