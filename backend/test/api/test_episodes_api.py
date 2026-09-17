from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from test.factories import PodcastEpisodeFactory


def test_list_episodes_empty(client: TestClient):
    response = client.get("/episodes")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_and_search_episodes(client: TestClient, db_session: Session):
    draft = PodcastEpisodeFactory.build(title="Draft day disasters")
    waiver = PodcastEpisodeFactory.build(title="Waiver wire wisdom")
    db_session.add_all([draft, waiver])
    db_session.commit()

    response = client.get("/episodes")
    assert response.status_code == 200
    titles = {item["title"] for item in response.json()["items"]}
    assert titles == {draft.title, waiver.title}

    response = client.get("/episodes", params={"search": "waiver"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == waiver.id


def test_read_episode(client: TestClient, db_session: Session):
    episode = PodcastEpisodeFactory.build()
    db_session.add(episode)
    db_session.commit()

    response = client.get(f"/episodes/{episode.id}")
    assert response.status_code == 200
    assert response.json()["guid"] == episode.guid

    response = client.get("/episodes/999999")
    assert response.status_code == 404
