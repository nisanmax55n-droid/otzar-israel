# אוצר ישראל

אוצר ישראל הוא פרויקט וובי בעברית וב־RTL שנועד להפוך למאגר יהודי אחוד של תנ״ך, משנה, תלמוד, מדרש, הלכה, תפילות וספרים נוספים.

## מצב נוכחי — MVP 0.1.0

הפרויקט כולל:

- Frontend: React + TypeScript + Vite
- Backend: FastAPI + SQLAlchemy
- PostgreSQL בפריסה ל־Railway, עם SQLite לפיתוח מקומי
- ספרייה, חיפוש ומסך קריאה
- מודל נתונים אחיד: ספר → מהדורה → קטעי טקסט
- מנגנון יבוא ראשוני מ־Sefaria Export
- שמירת מקור ורישיון לכל מהדורה
- חסימת יבוא/הצגה אוטומטית של מהדורות שאין להן רישיון שימוש מאומת
- Docker ו־Railway configs

## עיקרון רישוי

כל מהדורת טקסט חייבת לשמור מקור ורישיון. יבוא אוטומטי מיועד רק למהדורות שהרישיון שלהן מאומת ומתאים לשימוש בפרויקט. רישיונות מגבילים כגון NC אינם מאושרים אוטומטית.

## הרצה מקומית

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## תיעוד

- `docs/PROJECT_STATE.md` — מצב הפרויקט והמשך עבודה
- `docs/DATA_MODEL.md` — מבנה הנתונים

## יעד קרוב

היעד הבא הוא יבוא תנ״ך אמיתי ממקור בעל רישיון מאומת, חיבור PostgreSQL והעלאת גרסת MVP ל־Railway.
