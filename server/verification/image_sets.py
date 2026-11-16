"""Managed image collections. Uploaded images are normalized and stored transactionally."""
import hashlib
import json
import secrets
from io import BytesIO
from pathlib import Path
from random import SystemRandom

from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError

from .errors import require

ROOT = Path(__file__).resolve().parents[2]
ALL_SYSTEM = "system-all"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
SET_NAMES = {"system-brand": "星锁品牌原作", "system-orbit": "星际光轨", "system-material": "造物工坊",
             "system-nature": "自然梦境", "system-space": "空间实验"}


def system_catalog():
    entries = [dict(id="brand-" + name, name=label, set_id="system-brand",
                    path=ROOT / "assets" / "rotation" / f"starlock-{name}.png")
               for name, label in (("garden", "兰庭微光"), ("workshop", "星轨工坊"), ("aurora", "极光之钥"))]
    manifest = ROOT / "server" / "assets" / "image-sets" / "generated.json"
    if manifest.exists():
        for item in json.loads(manifest.read_text()):
            entries.append({**item, "path": manifest.parent / (item["id"] + ".png")})
    return {item["id"]: item for item in entries}


def normalize_upload(raw):
    require(0 < len(raw) <= MAX_UPLOAD_BYTES, "IMAGE_SIZE_INVALID", "单张图片不能超过 5 MB", 413)
    try:
        with Image.open(BytesIO(raw), formats=["PNG", "JPEG", "WEBP"]) as original:
            require(not getattr(original, "is_animated", False), "IMAGE_INVALID", "请上传静态图片")
            width, height = original.size
            require(min(width, height) >= 256 and max(width, height) <= 4096 and width * height <= 12_000_000,
                    "IMAGE_DIMENSIONS_INVALID", "图片每边需为 256–4096 像素，总像素不超过 1200 万")
            original.load()
            image = ImageOps.exif_transpose(original).convert("RGBA")
            background = Image.new("RGBA", image.size, "#f4f0f8")
            image = Image.alpha_composite(background, image).convert("RGB")
            require(max(ImageStat.Stat(image.resize((64, 64))).stddev) >= 8,
                    "IMAGE_TOO_PLAIN", "图片缺少可辨认细节，请选择有纹理或图案的图片")
            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            stream = BytesIO()
            image.save(stream, "JPEG", quality=90)
            return stream.getvalue(), image.width, image.height
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        from .errors import VerificationError
        raise VerificationError("IMAGE_INVALID", "图片无法读取，请使用 PNG、JPEG 或 WebP")


class ImageSetStore:
    def __init__(self, sites):
        self.sites = sites
        self.system = system_catalog()

    def initialize(self):
        with self.sites.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS image_set (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, source TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS image_asset (
                    id TEXT PRIMARY KEY, set_id TEXT NOT NULL, name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1, sha256 TEXT NOT NULL,
                    width INTEGER NOT NULL, height INTEGER NOT NULL, data BLOB,
                    UNIQUE(set_id,sha256), FOREIGN KEY(set_id) REFERENCES image_set(id)
                );
                CREATE TABLE IF NOT EXISTS image_policy (id INTEGER PRIMARY KEY CHECK(id=1), set_id TEXT NOT NULL);
                INSERT OR IGNORE INTO image_policy VALUES(1,'system-all');
            """)
            for sid, name in SET_NAMES.items():
                db.execute("INSERT OR IGNORE INTO image_set VALUES(?,?,?,1)", (sid, name, "system"))
            for item in self.system.values():
                with Image.open(item["path"]) as image:
                    db.execute("INSERT OR IGNORE INTO image_asset VALUES(?,?,?,1,?,?,?,NULL)",
                               (item["id"], item["set_id"], item["name"], hashlib.sha256(item["path"].read_bytes()).hexdigest(),
                                image.width, image.height))

    @staticmethod
    def available(db, set_id):
        if set_id == ALL_SYSTEM:
            return db.execute("SELECT a.id FROM image_asset a JOIN image_set s ON s.id=a.set_id WHERE a.active=1 AND s.active=1 AND s.source='system'").fetchall()
        return db.execute("SELECT a.id FROM image_asset a JOIN image_set s ON s.id=a.set_id WHERE a.active=1 AND s.active=1 AND s.id=?", (set_id,)).fetchall()

    def resolve(self, set_id=None):
        with self.sites.connect() as db:
            selected = set_id or db.execute("SELECT set_id FROM image_policy WHERE id=1").fetchone()[0]
            require(self.available(db, selected), "IMAGE_SET_UNAVAILABLE", "图片集未启用或没有可用图片", 409)
            return selected

    def list(self):
        with self.sites.connect() as db:
            rows = db.execute("SELECT s.*,COUNT(a.id) image_count,COALESCE(SUM(a.active),0) enabled_count FROM image_set s LEFT JOIN image_asset a ON a.set_id=s.id GROUP BY s.id ORDER BY s.source DESC,s.rowid").fetchall()
            default = db.execute("SELECT set_id FROM image_policy WHERE id=1").fetchone()[0]
        return {"sets": [dict(row) for row in rows], "default_set_id": default}

    def detail(self, set_id):
        with self.sites.connect() as db:
            row = db.execute("SELECT * FROM image_set WHERE id=?", (set_id,)).fetchone()
            require(row is not None, "IMAGE_SET_NOT_FOUND", "图片集不存在", 404)
            images = db.execute("SELECT id,name,active,width,height FROM image_asset WHERE set_id=? ORDER BY rowid", (set_id,)).fetchall()
        return {**dict(row), "images": [dict(image) for image in images]}

    def create(self, name):
        sid = "custom-" + secrets.token_hex(12)
        with self.sites.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            require(db.execute("SELECT COUNT(*) FROM image_set WHERE source='custom'").fetchone()[0] < 50,
                    "IMAGE_QUOTA", "自定义图片集已达到 50 个", 409)
            db.execute("INSERT INTO image_set VALUES(?,?,?,0)", (sid, name, "custom"))
        return self.detail(sid)

    def update(self, set_id, name, active):
        with self.sites.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            require(db.execute("SELECT 1 FROM image_set WHERE id=?", (set_id,)).fetchone(),
                    "IMAGE_SET_NOT_FOUND", "图片集不存在", 404)
            if active:
                require(db.execute("SELECT 1 FROM image_asset WHERE set_id=? AND active=1", (set_id,)).fetchone(),
                        "IMAGE_SET_EMPTY", "请先上传并启用至少一张图片", 409)
            db.execute("UPDATE image_set SET name=?,active=? WHERE id=?", (name, int(active), set_id))
            self._check_default(db)
        return self.detail(set_id)

    def _check_default(self, db):
        default = db.execute("SELECT set_id FROM image_policy WHERE id=1").fetchone()[0]
        require(self.available(db, default), "DEFAULT_SET_EMPTY", "此操作会使默认图库不可用，请先更换默认图片集", 409)

    def set_default(self, set_id):
        with self.sites.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            require(self.available(db, set_id), "IMAGE_SET_UNAVAILABLE", "请先启用有图片的图集", 409)
            db.execute("UPDATE image_policy SET set_id=? WHERE id=1", (set_id,))
        return self.list()

    def upload(self, set_id, name, raw):
        data, width, height = normalize_upload(raw)
        sha = hashlib.sha256(data).hexdigest()
        with self.sites.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT source FROM image_set WHERE id=?", (set_id,)).fetchone()
            require(row is not None, "IMAGE_SET_NOT_FOUND", "图片集不存在", 404)
            require(row[0] == "custom", "SYSTEM_SET_READONLY", "请将自己的图片上传到自定义图片集", 409)
            existing = db.execute("SELECT id FROM image_asset WHERE set_id=? AND sha256=?", (set_id, sha)).fetchone()
            if existing:
                return {"id": existing[0], "duplicate": True}
            require(db.execute("SELECT COUNT(*) FROM image_asset WHERE set_id=?", (set_id,)).fetchone()[0] < 200,
                    "IMAGE_QUOTA", "每个图片集最多保存 200 张图片", 409)
            aid = "img-" + secrets.token_hex(16)
            db.execute("INSERT INTO image_asset VALUES(?,?,?,1,?,?,?,?)", (aid, set_id, name, sha, width, height, data))
        return {"id": aid, "duplicate": False}

    def set_image_active(self, asset_id, active):
        with self.sites.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT set_id FROM image_asset WHERE id=?", (asset_id,)).fetchone()
            require(row is not None, "IMAGE_NOT_FOUND", "图片不存在", 404)
            db.execute("UPDATE image_asset SET active=? WHERE id=?", (int(active), asset_id))
            self._check_default(db)
        return self.detail(row[0])

    def image(self, asset_id):
        with self.sites.connect() as db:
            row = db.execute("SELECT data FROM image_asset WHERE id=?", (asset_id,)).fetchone()
        require(row is not None, "IMAGE_NOT_FOUND", "图片不存在", 404)
        if row[0] is not None:
            stream = BytesIO(row[0])
        else:
            require(asset_id in self.system, "IMAGE_NOT_FOUND", "系统图片不存在", 404)
            stream = self.system[asset_id]["path"]
        with Image.open(stream) as image:
            return image.convert("RGB").copy()

    def sample(self, set_id):
        with self.sites.connect() as db:
            candidates = self.available(db, set_id)
        require(candidates, "IMAGE_SET_UNAVAILABLE", "图片集未启用或没有可用图片", 409)
        return self.image(SystemRandom().choice(candidates)[0])
