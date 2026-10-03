"""S2-A: Categories — depth calculation, cycle detection, relocation, 403/409."""
import pytest
import uuid


@pytest.mark.asyncio
async def test_create_root_category(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    resp = await client.post("/api/v1/admin/categories", headers=headers,
                              json={"name": "Electronics", "slug": "electronics"})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["depth"] == 1
    assert data["parent_id"] is None
    assert data["name"] == "Electronics"


@pytest.mark.asyncio
async def test_create_child_category_depth(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    root = await client.post("/api/v1/admin/categories", headers=headers,
                              json={"name": "Root", "slug": "root"})
    root_id = root.json()["id"]

    child = await client.post("/api/v1/admin/categories", headers=headers,
                               json={"name": "Child", "slug": "child", "parent_id": root_id})
    assert child.status_code == 201
    assert child.json()["depth"] == 2

    grandchild = await client.post("/api/v1/admin/categories", headers=headers,
                                    json={"name": "Grand", "slug": "grand", "parent_id": child.json()["id"]})
    assert grandchild.status_code == 201
    assert grandchild.json()["depth"] == 3


@pytest.mark.asyncio
async def test_depth_exceeded_400(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    r1 = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "L1", "slug": "l1"})
    l1_id = r1.json()["id"]
    r2 = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "L2", "slug": "l2", "parent_id": l1_id})
    l2_id = r2.json()["id"]
    r3 = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "L3", "slug": "l3", "parent_id": l2_id})
    l3_id = r3.json()["id"]
    r4 = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "L4", "slug": "l4", "parent_id": l3_id})
    assert r4.status_code == 400, r4.text


@pytest.mark.asyncio
async def test_self_parent_400(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    r = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "Self", "slug": "self"})
    cat_id = r.json()["id"]
    resp = await client.patch(f"/api/v1/admin/categories/{cat_id}", headers=headers,
                               json={"name": "Self", "slug": "self", "parent_id": cat_id})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cycle_detection_400(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    a = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "A", "slug": "cat-a"})
    b = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "B", "slug": "cat-b", "parent_id": a.json()["id"]})
    c = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "C", "slug": "cat-c", "parent_id": b.json()["id"]})
    # Try to move A under C (cycle)
    resp = await client.patch(f"/api/v1/admin/categories/{a.json()['id']}", headers=headers,
                               json={"name": "A", "slug": "cat-a", "parent_id": c.json()["id"]})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_relocate_subtree(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    root1 = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "R1", "slug": "r1"})
    child1 = await client.post("/api/v1/admin/categories", headers=headers,
                                json={"name": "C1", "slug": "c1", "parent_id": root1.json()["id"]})
    root2 = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "R2", "slug": "r2"})
    # Relocate root1 under root2
    resp = await client.patch(f"/api/v1/admin/categories/{root1.json()['id']}", headers=headers,
                               json={"name": "R1", "slug": "r1", "parent_id": root2.json()["id"]})
    assert resp.status_code == 200
    node = resp.json()
    assert node["depth"] == 2
    # Child should also be relocated
    assert len(node["children"]) == 1
    assert node["children"][0]["depth"] == 3


@pytest.mark.asyncio
async def test_category_slug_duplicate_409(client, user_a, shop_a):
    headers = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    await client.post("/api/v1/admin/categories", headers=headers, json={"name": "Cat", "slug": "dup-slug"})
    resp = await client.post("/api/v1/admin/categories", headers=headers, json={"name": "Cat2", "slug": "dup-slug"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_category_foreign_parent_403(client, user_a, shop_a, user_b, shop_b):
    headers_a = {**user_a["auth_headers"], "X-Shop-Id": str(shop_a["shop_id"])}
    # Create category in shop B
    headers_b = {**user_b["auth_headers"], "X-Shop-Id": str(shop_b["shop_id"])}
    b_cat = await client.post("/api/v1/admin/categories", headers=headers_b, json={"name": "B", "slug": "b-cat"})
    b_cat_id = b_cat.json()["id"]
    # Try to create category in shop A with parent from shop B
    resp = await client.post("/api/v1/admin/categories", headers=headers_a,
                              json={"name": "Child", "slug": "child-of-b", "parent_id": b_cat_id})
    assert resp.status_code == 403
