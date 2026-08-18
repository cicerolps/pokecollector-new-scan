from app.db.models import Card, CollectionItem


def _seed_card(db_session, card_id="a") -> None:
    db_session.add(
        Card(
            id=card_id,
            source_api="tcgdex",
            name="Charizard",
            set_id="base1",
            set_name="Base",
            number="4/102",
            rarity="Rare Holo",
        )
    )
    db_session.commit()


def test_get_card_returns_404_for_unknown_card(client):
    response = client.get("/api/v1/cards/does-not-exist")
    assert response.status_code == 404


def test_get_card_returns_card_details(client, db_session):
    _seed_card(db_session)
    response = client.get("/api/v1/cards/a")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "a"
    assert body["name"] == "Charizard"
    assert body["number"] == "4/102"


def test_list_collection_starts_empty(client):
    response = client.get("/api/v1/collection")
    assert response.status_code == 200
    assert response.json() == []


def test_add_to_collection_rejects_unknown_card(client):
    response = client.post("/api/v1/collection", json={"card_id": "does-not-exist"})
    assert response.status_code == 404


def test_add_to_collection_then_list(client, db_session):
    _seed_card(db_session)

    add_response = client.post(
        "/api/v1/collection",
        json={"card_id": "a", "quantity": 2, "condition": "NM", "language": "en"},
    )
    assert add_response.status_code == 201
    added = add_response.json()
    assert added["card"]["id"] == "a"
    assert added["quantity"] == 2

    list_response = client.get("/api/v1/collection")
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["id"] == added["id"]
    assert items[0]["card"]["name"] == "Charizard"


def test_add_to_collection_defaults_quantity_to_one(client, db_session):
    _seed_card(db_session)
    response = client.post("/api/v1/collection", json={"card_id": "a"})
    assert response.status_code == 201
    assert response.json()["quantity"] == 1


def test_list_collection_skips_items_whose_card_disappeared(client, db_session):
    _seed_card(db_session)
    db_session.add(CollectionItem(card_id="a", quantity=1))
    db_session.commit()
    db_session.query(Card).filter(Card.id == "a").delete()
    db_session.commit()

    response = client.get("/api/v1/collection")
    assert response.status_code == 200
    assert response.json() == []
