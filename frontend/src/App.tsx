import {useEffect,useMemo,useState} from 'react'
import {BarChart3,BookOpen,ChevronLeft,ChevronRight,Library,Moon,Search,ScrollText,Sparkles,Sun} from 'lucide-react'
import {api,SearchHit,Stats,TorahBook,TorahParasha,TorahVerse} from './services/api'
import './home.css'

type View='home'|'tanakh'|'torah'|'book'|'parasha'|'bookView'|'search'

const homeCategories=[
  ['tanakh','תנ״ך','תורה, נביאים וכתובים'],
  ['mishnah','משנה','שישה סדרי משנה'],
  ['talmud','תלמוד','בבלי וירושלמי'],
  ['halakha','הלכה','רמב״ם, טור ושולחן ערוך'],
  ['prayer','תפילה','סידורים, מחזורים ופיוטים'],
  ['midrash','מדרש','מדרשי חז״ל'],
  ['musar','מוסר','ספרי מוסר ומחשבה'],
  ['chasidut','חסידות','ספרי חסידות'],
]

function heNumber(n:number){
  if(n<=0)return String(n)
  const ones=['','א׳','ב׳','ג׳','ד׳','ה׳','ו׳','ז׳','ח׳','ט׳']
  const tens=['','י׳','כ׳','ל׳','מ׳','נ׳','ס׳','ע׳','פ׳','צ׳']
  if(n<10)return ones[n]
  if(n===15)return 'ט״ו'
  if(n===16)return 'ט״ז'
  if(n<20)return `י״${ones[n-10].replace('׳','')}`
  const t=Math.floor(n/10),o=n%10
  if(!o)return tens[t]
  return `${tens[t].replace('׳','')}״${ones[o].replace('׳','')}`
}

export default function App(){
  const[view,setView]=useState<View>('home')
  const[dark,setDark]=useState(false)
  const[busy,setBusy]=useState(false)
  const[stats,setStats]=useState<Stats|null>(null)
  const[q,setQ]=useState('')
  const[hits,setHits]=useState<SearchHit[]>([])
  const[books,setBooks]=useState<TorahBook[]>([])
  const[selectedBook,setSelectedBook]=useState<TorahBook|null>(null)
  const[parashot,setParashot]=useState<TorahParasha[]>([])
  const[selectedParasha,setSelectedParasha]=useState<TorahParasha|null>(null)
  const[currentChapter,setCurrentChapter]=useState<number|null>(null)
  const[verses,setVerses]=useState<TorahVerse[]>([])
  const[bookVerses,setBookVerses]=useState<TorahVerse[]>([])

  useEffect(()=>{document.documentElement.dataset.theme=dark?'dark':'light'},[dark])
  useEffect(()=>{api.stats().then(setStats).catch(()=>{})},[])

  function openLibrary(){
    setView('home')
    setTimeout(()=>document.getElementById('library')?.scrollIntoView({behavior:'smooth'}),0)
  }

  async function runSearch(e?:React.FormEvent){
    e?.preventDefault()
    if(q.trim().length<2)return
    setBusy(true)
    try{setHits(await api.search(q.trim()));setView('search')}finally{setBusy(false)}
  }

  async function openTorah(){
    setBusy(true)
    try{setBooks(await api.torahBooks());setView('torah')}finally{setBusy(false)}
  }

  async function openBook(book:TorahBook){
    setBusy(true)
    try{
      setSelectedBook(book)
      setSelectedParasha(null)
      setParashot(await api.torahParashot(book.slug))
      setView('book')
    }finally{setBusy(false)}
  }

  async function openParasha(parasha:TorahParasha){
    if(!selectedBook)return
    setBusy(true)
    try{
      setSelectedParasha(parasha)
      setCurrentChapter(parasha.start_chapter)
      setVerses(await api.torahParashaChapter(parasha.id,parasha.start_chapter))
      setView('parasha')
      window.scrollTo({top:0})
    }finally{setBusy(false)}
  }

  async function changeParashaChapter(chapter:number){
    if(!selectedParasha)return
    setBusy(true)
    try{
      setCurrentChapter(chapter)
      setVerses(await api.torahParashaChapter(selectedParasha.id,chapter))
      window.scrollTo({top:0,behavior:'smooth'})
    }finally{setBusy(false)}
  }

  async function openBookView(){
    if(!selectedBook)return
    setBusy(true)
    try{
      setBookVerses(await api.torahBookView(selectedBook.slug))
      setView('bookView')
      window.scrollTo({top:0})
    }finally{setBusy(false)}
  }

  const chapterGroups=useMemo(()=>{
    const groups=new Map<number,TorahVerse[]>()
    bookVerses.forEach(v=>groups.set(v.chapter,[...(groups.get(v.chapter)||[]),v]))
    return [...groups.entries()]
  },[bookVerses])

  const parashaChapterIndex=selectedParasha&&currentChapter?selectedParasha.chapters.indexOf(currentChapter):-1
  const prevChapter=selectedParasha&&parashaChapterIndex>0?selectedParasha.chapters[parashaChapterIndex-1]:null
  const nextChapter=selectedParasha&&parashaChapterIndex>=0?selectedParasha.chapters[parashaChapterIndex+1]||null:null

  return <div className="app">
    <header>
      <button className="brand" onClick={()=>setView('home')}><span className="mark">א</span><span><b>אוצר ישראל</b><small>ארון הספרים היהודי</small></span></button>
      <nav><button onClick={()=>setView('home')}>בית</button><button onClick={openLibrary}>ספרייה</button><button onClick={()=>{setQ('');setHits([]);setView('search')}}>חיפוש</button></nav>
      <button className="icon" onClick={()=>setDark(!dark)}>{dark?<Sun/>:<Moon/>}</button>
    </header>

    <main>
      {view==='home'&&<>
        <section className="hero">
          <div className="kicker"><Sparkles size={16}/> כל ארון הספרים היהודי במקום אחד</div>
          <h1>לגלות. ללמוד. להתפלל.<br/><span>אוצר ישראל.</span></h1>
          <p>מאגר יהודי פתוח שמחבר תנ״ך, חז״ל, הלכה, תפילה, מחשבה ופרשנות למרחב לימוד אחד.</p>
          <form className="searchbox" onSubmit={runSearch}><Search/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="חפש פסוק, ביטוי, ספר או נושא..."/><button>חיפוש</button></form>
          {stats&&<div className="stats"><div><BarChart3/><b>{stats.works.toLocaleString()}</b><span>ספרים</span></div><div><ScrollText/><b>{stats.segments.toLocaleString()}</b><span>קטעי טקסט</span></div><div><Library/><b>{stats.categories.length}</b><span>קטגוריות</span></div></div>}
        </section>

        <section className="section" id="library">
          <div className="sectionHead"><div><span>הספרייה</span><h2>פתח את ארון הספרים</h2></div></div>
          <div className="grid">{homeCategories.map(([key,title,desc])=><button key={key} className="category" onClick={()=>key==='tanakh'&&setView('tanakh')} disabled={key!=='tanakh'}><BookOpen/><b>{title}</b><span>{desc}</span>{key==='tanakh'?<small>פתוח לקריאה</small>:<small>בהמשך</small>}</button>)}</div>
        </section>

        <section className="features"><div><ScrollText/><b>מקור ורישיון לכל טקסט</b><span>כל מהדורה נשמרת עם מקור שימוש ברור.</span></div><div><Search/><b>חיפוש עברי מנורמל</b><span>חיפוש גם בטקסט מנוקד ובכתיב משתנה.</span></div><div><Library/><b>מבנה שמוכן לגדול</b><span>מתוכנן מראש לארון ספרים יהודי רחב.</span></div></section>
      </>}

      {view==='search'&&<section className="page">
        <div className="pageTitle"><span>חיפוש</span><h1>חיפוש באוצר ישראל</h1></div>
        <form className="searchbox compact" onSubmit={runSearch}><Search/><input autoFocus value={q} onChange={e=>setQ(e.target.value)} placeholder="מה תרצה למצוא?"/><button>חיפוש</button></form>
        {busy?<div className="empty">מחפש…</div>:hits.length?<div className="results">{hits.map((h,i)=><div className="resultCard" key={i}><b>{h.work_title}</b><small>{h.ref}</small><p>{h.text}</p></div>)}</div>:q?<div className="empty">לא נמצאו תוצאות.</div>:<div className="empty"><Search/><b>חיפוש בכל ארון הספרים</b><span>כתוב לפחות שתי אותיות כדי להתחיל.</span></div>}
      </section>}

      {view==='tanakh'&&<section className="page">
        <div className="breadcrumbs"><button onClick={()=>setView('home')}>בית</button><ChevronLeft/> <b>תנ״ך</b></div>
        <div className="pageTitle"><span>תנ״ך</span><h1>תורה · נביאים · כתובים</h1></div>
        <div className="grid threeGrid">
          <button className="category primaryCard" onClick={openTorah}><ScrollText/><b>תורה</b><span>חמשת חומשי תורה, פרשות, פרקים ופסוקים</span></button>
          <button className="category" disabled><BookOpen/><b>נביאים</b><span>ייבנה בשלב הבא</span><small>בקרוב</small></button>
          <button className="category" disabled><Library/><b>כתובים</b><span>ייבנה בשלב הבא</span><small>בקרוב</small></button>
        </div>
      </section>}

      {view==='torah'&&<section className="page">
        <div className="breadcrumbs"><button onClick={()=>setView('tanakh')}>תנ״ך</button><ChevronLeft/><b>תורה</b></div>
        <div className="pageTitle"><span>תורה</span><h1>חמשת חומשי תורה</h1><p>בחר חומש כדי לעבור לפרשות או לתצוגת הספר המלאה.</p></div>
        {busy?<div className="empty">טוען את התורה…</div>:books.length===0?<div className="empty"><BookOpen/><b>התורה עדיין נטענת למאגר</b></div>:<div className="grid fiveGrid">{books.map(book=><button className="category bookCard" key={book.id} onClick={()=>openBook(book)}><ScrollText/><b>{book.title_he}</b><span>{book.chapter_count} פרקים</span><small>{book.license}</small></button>)}</div>}
      </section>}

      {view==='book'&&selectedBook&&<section className="page">
        <div className="breadcrumbs"><button onClick={openTorah}>תורה</button><ChevronLeft/><b>{selectedBook.title_he}</b></div>
        <div className="bookHero"><div><span>חומש</span><h1>{selectedBook.title_he}</h1><p>{selectedBook.chapter_count} פרקים · טקסט עברי מנוקד</p></div><button className="bookViewButton" onClick={openBookView}><BookOpen/> תצוגת ספר מלאה</button></div>
        <div className="sectionHead"><div><span>לפי פרשות</span><h2>פרשות ספר {selectedBook.title_he}</h2></div></div>
        {busy?<div className="empty">טוען…</div>:<div className="parashaGrid">{parashot.map(p=><button className="parashaCard" key={p.id} onClick={()=>openParasha(p)}><small>פרשה {p.order}</small><b>פרשת {p.title_he}</b><span>{p.chapters.length===1?`פרק ${heNumber(p.start_chapter)}`:`פרקים ${heNumber(p.start_chapter)}–${heNumber(p.end_chapter)}`}</span><ChevronLeft/></button>)}</div>}
        <div className="sourceNote">מקור הטקסט: {selectedBook.source_name} · רישיון: {selectedBook.license}</div>
      </section>}

      {view==='parasha'&&selectedBook&&selectedParasha&&<section className="readerShell">
        <aside className="readerSidebar">
          <button className="backLink" onClick={()=>setView('book')}><ChevronRight/> חזרה לספר {selectedBook.title_he}</button>
          <span>ספר {selectedBook.title_he}</span><h2>פרשת {selectedParasha.title_he}</h2>
          <b>פרקים בפרשה</b>
          <div className="chapterButtons">{selectedParasha.chapters.map(ch=><button key={ch} className={ch===currentChapter?'active':''} onClick={()=>changeParashaChapter(ch)}>פרק {heNumber(ch)}</button>)}</div>
        </aside>
        <article className="torahReader">
          <div className="readerHeading"><small>ספר {selectedBook.title_he} · פרשת {selectedParasha.title_he}</small><h1>פרק {currentChapter?heNumber(currentChapter):''}</h1></div>
          {busy?<div className="empty">טוען…</div>:<div className="verses">{verses.map(v=><p key={v.id}><sup>{heNumber(v.verse)}</sup>{v.text}</p>)}</div>}
          <div className="pager"><button disabled={!prevChapter} onClick={()=>prevChapter&&changeParashaChapter(prevChapter)}><ChevronRight/> פרק קודם</button><button disabled={!nextChapter} onClick={()=>nextChapter&&changeParashaChapter(nextChapter)}>פרק הבא <ChevronLeft/></button></div>
        </article>
      </section>}

      {view==='bookView'&&selectedBook&&<section className="bookReaderPage">
        <div className="bookReaderHeader"><button className="backLink" onClick={()=>setView('book')}><ChevronRight/> חזרה לפרשות</button><span>תצוגת ספר</span><h1>ספר {selectedBook.title_he}</h1><p>מהפסוק הראשון ועד הפסוק האחרון, ברצף מלא.</p></div>
        {busy?<div className="empty">טוען את הספר…</div>:<article className="fullBook">{chapterGroups.map(([chapter,chapterVerses])=><section className="bookChapter" key={chapter}><h2>פרק {heNumber(chapter)}</h2><div className="verses">{chapterVerses.map(v=><p key={v.id}><sup>{heNumber(v.verse)}</sup>{v.text}</p>)}</div></section>)}</article>}
      </section>}
    </main>
    <footer>אוצר ישראל · ארון הספרים היהודי</footer>
  </div>
}
