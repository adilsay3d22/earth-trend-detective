"""Check EONET event placement. Run: .venv/Scripts/python.exe -m app.test_events"""
from app.server import event_spot

box = (21.9, 87.9, 25.9, 91.9)  # s, w, n, e around Bangladesh
pt = lambda lon, lat: {"type": "Point", "coordinates": [lon, lat], "date": "2020-05-16T00:00:00Z"}
poly = lambda ring: {"type": "Polygon", "coordinates": [ring], "date": "2016-05-21T00:00:00Z"}

storm = {"sources": [{"id": "JTWC"}], "geometry": [pt(85, 15), pt(89, 23)]}           # track enters the box later
assert event_spot(storm, box) == (89, 23, "2020-05-16")
gdacs = {"sources": [{"id": "GDACS"}], "geometry": [poly([[23.6, 89.0], [23.8, 89.2]])]}  # GDACS writes [lat, lon]
assert [round(v, 2) for v in event_spot(gdacs, box)[:2]] == [89.1, 23.7]
idc = {"sources": [{"id": "IDC"}], "geometry": [poly([[89.4, 22.0], [89.4, 23.4]])]}     # everyone else [lon, lat]
assert [round(v, 2) for v in event_spot(idc, box)[:2]] == [89.4, 22.7]
chile = {"sources": [{"id": "GDACS"}], "geometry": [poly([[-33.1, -71.6], [-33.2, -71.7]])]}
assert event_spot(chile, (-90, -180, -55, 180)) is None                                 # not in Antarctica
print("events OK")
