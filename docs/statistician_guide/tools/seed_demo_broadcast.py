"""Seed the fictional demo broadcast used by the statistician guide.

Talks only to the isolated instance started by run_demo_instance.py. Creates
two invented schools (Northgate, Riverside), a small invented roster for
each, and broadcast FB-DEMO-GUIDE-001, then loads it, takes it live and hands
game-data control to the Statistician console -- i.e. the state a volunteer
statistician finds when they open their screen.

A throwaway operator PIN is generated per runtime and written to
<runtime_dir>/demo_pin.txt (it never leaves the scratch runtime).

Usage:  .venv/Scripts/python.exe docs/statistician_guide/tools/seed_demo_broadcast.py <runtime_dir> [port]
"""

from __future__ import annotations

import http.cookiejar
import json
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

SEASON = "2026"

SCHOOLS = {
    "home": {
        "official_name": "Northgate High School (DEMO)",
        "broadcast_name": "Northgate",
        "short_name": "Northgate",
        "preferred_scorebug_name": "NORTHGATE",
        "nickname": "Falcons",
        "mascot": "Falcon",
        "city": "Demo City",
        "state": "XX",
        "classification": "Demo",
        "primary_color": "#1F4E9C",
        "secondary_color": "#F2B705",
        "programs": {"Football": {}},
    },
    "visitor": {
        "official_name": "Riverside High School (DEMO)",
        "broadcast_name": "Riverside",
        "short_name": "Riverside",
        "preferred_scorebug_name": "RIVERSIDE",
        "nickname": "Otters",
        "mascot": "Otter",
        "city": "Demo Town",
        "state": "XX",
        "classification": "Demo",
        "primary_color": "#0F7B5F",
        "secondary_color": "#FFFFFF",
        "programs": {"Football": {}},
    },
}

# Invented players. Northgate carries #88; Riverside deliberately has no #88
# (the guide's team-mismatch example) and no #44 (the off-roster example).
ROSTERS = {
    "home": [
        ("7", "Marcus", "Hale", "QB"),
        ("22", "Devin", "Okafor", "RB"),
        ("4", "Tyler", "Brandt", "WR"),
        ("11", "Jalen", "Pierce", "WR"),
        ("88", "Owen", "Castillo", "TE"),
        ("3", "Eli", "Sanderson", "K"),
        ("52", "Grant", "Whitfield", "LB"),
        ("21", "Andre", "Lyle", "CB"),
        ("9", "Noah", "Kessler", "S"),
        ("95", "Caleb", "Rourke", "DL"),
        ("30", "Isaiah", "Moran", "LB"),
        ("17", "Luke", "Danvers", "WR"),
    ],
    "visitor": [
        ("12", "Bryce", "Talbot", "QB"),
        ("5", "Jordan", "Reyes", "RB"),
        ("1", "Kai", "Holloway", "WR"),
        ("80", "Mason", "Albright", "WR"),
        ("85", "Reid", "Fenwick", "TE"),
        ("15", "Sam", "Ostrander", "K"),
        ("54", "Darius", "Coleman", "LB"),
        ("24", "Trent", "Vaughn", "CB"),
        ("2", "Xavier", "Blount", "S"),
        ("99", "Hunter", "Graves", "DL"),
        ("33", "Cole", "Mercer", "LB"),
        ("19", "Ian", "Prescott", "WR"),
    ],
}


class Client:
    def __init__(self, base: str) -> None:
        self.base = base
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def call(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body or {}).encode() if method != "GET" else None
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self.opener.open(request) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"null")


def main() -> None:
    runtime = Path(sys.argv[1]).resolve()
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5072
    client = Client(f"http://127.0.0.1:{port}")

    pin_file = runtime / "demo_pin.txt"
    if pin_file.exists():
        pin = pin_file.read_text().strip()
        status, body = client.call("POST", "/api/login", {"pin": pin})
    else:
        pin = "".join(secrets.choice("0123456789") for _ in range(6))
        status, body = client.call("POST", "/api/setup-pin", {"pin": pin, "confirm": pin})
        if status == 200:
            pin_file.write_text(pin)
    assert status == 200, (status, body)

    school_ids = {}
    for side, school in SCHOOLS.items():
        status, body = client.call("POST", "/api/schools", school)
        assert status == 201, (status, body)
        school_ids[side] = body["id"]
        status, roster = client.call(
            "POST",
            "/api/rosters",
            {"school_id": body["id"], "sport": "Football", "season": SEASON,
             "level": "Varsity", "division": "Boys"},
        )
        assert status == 201, (status, roster)
        for number, first, last, position in ROSTERS[side]:
            status, player = client.call(
                "POST",
                f"/api/rosters/{roster['id']}/players",
                {"number": number, "first_name": first, "last_name": last,
                 "position": position, "grade": "11", "active": True},
            )
            assert status == 201, (status, player)

    status, body = client.call(
        "POST",
        "/api/create-broadcast",
        {"sport": "Football", "season": SEASON, "week": "1",
         "home_school_id": school_ids["home"], "visitor_school_id": school_ids["visitor"],
         "venue": "Northgate Memorial Stadium (DEMO)", "contest_type": "scrimmage",
         "date": "2026-10-23", "scheduled_start": "07:00 PM"},
    )
    assert status in (200, 201), (status, body)
    broadcast_id = body.get("broadcast", body).get("broadcast_id")
    assert broadcast_id == "FB-DEMO-GUIDE-001", broadcast_id

    for path in (f"/api/broadcasts/{broadcast_id}/load", "/api/start-broadcast"):
        status, body = client.call("POST", path)
        assert status == 200, (path, status, body)
    status, body = client.call("POST", "/api/control-source", {"authority": "statistician"})
    assert status == 200, (status, body)
    print(json.dumps({"broadcast_id": broadcast_id, "schools": school_ids,
                      "authority": body.get("game_data_authority")}, indent=2))


if __name__ == "__main__":
    main()
