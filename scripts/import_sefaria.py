#!/usr/bin/env python3
import argparse
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.services.sefaria_importer import SefariaImporter


def main():
    p=argparse.ArgumentParser(description='Import licensed Jewish texts from Sefaria Export into Otzar Israel')
    p.add_argument('--category',default='Tanakh')
    p.add_argument('--limit',type=int,default=5)
    p.add_argument('--preview',action='store_true')
    args=p.parse_args()
    db:Session=SessionLocal()
    try:
        importer=SefariaImporter(db)
        records=importer.preview(category=args.category,limit=args.limit)
        if args.preview:
            for r in records: print(r)
            return
        for record in records:
            print(importer.import_book_record(record))
    finally: db.close()

if __name__=='__main__': main()
