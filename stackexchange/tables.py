from collections import OrderedDict
from tqdm import tqdm
import xml.etree.ElementTree as ET
from sqlite3 import Error, IntegrityError

# Ability to create schema
# and insert rows
class Table:
    
    def __init__(self, name, schema, constraints=[]):
        super().__init__()
        self.name = name
        self.schema = schema
        self.constraints = constraints
        
    def create_if_not_exists(self, db):
        columns = [f"{col} {typ}" for col, (_, typ) in self.schema.items()]
        create_sql = f"""CREATE TABLE IF NOT EXISTS {self.name} ({", ".join(columns + self.constraints)});"""
        db.execute(create_sql)
        
    def parse_row(self, xml_root):
        vals = OrderedDict()
        for col, (attr, typ) in self.schema.items():
            if attr in xml_root.attrib:
                v = xml_root.attrib[attr]
                # Convert to int
                if typ.startswith("INTEGER"):
                    v = int(v)
                vals[col] = v
            else:
                vals[col] = None
        return vals
    
    def insert_from_xml(self, db, path, exist_ok=False, filter_row=None, description=None):
        fd = open(path, "r")
        it = iter(fd)
        # Skip first two lines (xml opening tags)
        for i in range(2):
            next(it)
        
        last_row = None
        done = False
        def pull_rows():
            nonlocal last_row
            nonlocal done
            endtag = f"</{self.name}>"
            record_count = sum(1 for _ in open(path, "r")) - 3
            for line in tqdm(it, total=record_count, desc=description, leave=False):
                line = line.strip()
                if line == endtag:
                    break

                root = ET.fromstring(line)
                row = self.parse_row(root)

                if filter_row is not None:
                    row = filter_row(row)
                if row is None:
                    continue

                last_row = row
                yield list(row.values())
            done = True

        insert_sql = f"""INSERT{" OR IGNORE" if exist_ok else ""} INTO {self.name} ({",".join(self.schema.keys())}) VALUES ({",".join(["?" for _ in range(len(self.schema))])});"""
        
        data = pull_rows()
        cur = db.cursor()

        while not done:
            try:
                cur.executemany(insert_sql, data)
            except IntegrityError as e:
                continue # skip
            except Error as e:
                print("Last inserted row:")
                print(last_row)
                print("Exception:")
                raise e

        db.commit()
        cur.close()
        fd.close()

# More info here:
# https://meta.stackexchange.com/questions/2677/database-schema-documentation-for-the-public-data-dump-and-sede

sites = Table("sites",
    schema=OrderedDict([
        ("id",              ("Id",              "INTEGER PRIMARY KEY"   )),
        ("url",             ("Url",             "TEXT"                  )),
        ("tiny_name",       ("TinyName",        "TEXT"                  )),
        ("long_name",       ("LongName",        "TEXT"                  )),
        ("name",            ("Name",            "TEXT"                  )),
        ("parent_id",       ("ParentId",        "INTEGER"               )),
        ("tagline",         ("Tagline",         "TEXT"                  )),
        ("badge_icon_url",  ("BadgeIconUrl",    "TEXT"                  ))]),
    constraints=[]
)

posts = Table("posts",
    schema=OrderedDict([
        ("id",                  ("Id",                  "INTEGER"                       )),
        ("site_id",             (None,                  "INTEGER"                       )),
        ("post_type",           ("PostTypeId",          "INTEGER NOT NULL"              )),
        ("accepted_answer_id",  ("AcceptedAnswerId",    "INTEGER"                       )),
        ("creation_date",       ("CreationDate",        "TEXT NOT NULL"                 )),
        ("score",               ("Score",               "INTEGER NOT NULL"              )),
        ("view_count",          ("ViewCount",           "INTEGER"                       )),
        ("body",                ("Body",                "TEXT"                          )),
        ("user_id",             ("OwnerUserId",         "INTEGER"                       )),
        ("last_activity_date",  ("LastActivityDate",    "TEXT"                          )),
        ("title",               ("Title",               "TEXT"                          )),
        ("tags",                ("Tags",                "TEXT"                          )),
        ("answer_count",        ("AnswerCount",         "INTEGER"                       )),
        ("comment_count",       ("CommentCount",        "INTEGER"                       ))]), 
    constraints=[
        "PRIMARY KEY (id, site_id)",
        "FOREIGN KEY (site_id) REFERENCES sites (id)",
        "FOREIGN KEY (user_id, site_id) REFERENCES users (id, site_id)",
        "FOREIGN KEY (accepted_answer_id, site_id) REFERENCES posts (id, site_id)"
    ]
)

users = Table("users",
    schema=OrderedDict([
        ("id",              ("Id",              "INTEGER"           )),
        ("site_id",         (None,              "INTEGER"           )),
        ("reputation",      ("Reputation",      "INTEGER NOT NULL"  )),
        ("creation_date",   ("CreationDate",    "TEXT"              )),
        ("display_name",    ("DisplayName",     "TEXT"              )),
        ("url",             ("WebsiteUrl",      "TEXT"              )),
        ("location",        ("Location",        "TEXT"              )),
        ("about_me",        ("AboutMe",         "TEXT"              )),
        ("views",           ("Views",           "INTEGER"           )),
        ("profile_image",   ("ProfileImageUrl", "TEXT"              )),
        ("account_id",      ("AccountId",       "INTEGER"           )),
        ("up_votes",        ("UpVotes",         "INTEGER"           ))]),
    constraints=[
        "PRIMARY KEY (id, site_id)",
        "FOREIGN KEY (site_id) REFERENCES sites (id)"
    ]
)
