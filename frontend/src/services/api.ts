export type Work={id:number;slug:string;title_he:string;title_en?:string;category:string;subcategory?:string;author?:string}
export type Segment={id:number;ref:string;section_title?:string;level1?:number;level2?:number;level3?:number;position:number;text:string}
export type SearchHit={work_id:number;work_title:string;ref:string;text:string}
export type CategoryStat={name:string;count:number}
export type Stats={works:number;versions:number;segments:number;verified_versions:number;categories:CategoryStat[]}
export type SectionInfo={level1:number;count:number}
export type TanakhBook={id:number;slug:string;title_he:string;title_en:string;book_order:number;chapter_count:number;source_name:string;license:string}
export type TorahBook=TanakhBook
export type NeviimBook=TanakhBook
export type KetuvimBook=TanakhBook
export type TorahParasha={id:number;title_he:string;title_en:string;order:number;whole_ref:string;start_chapter:number;start_verse:number;end_chapter:number;end_verse:number;chapters:number[]}
export type TorahVerse={id:number;chapter:number;verse:number;text:string;ref:string}
export type NeviimVerse=TorahVerse
export type KetuvimVerse=TorahVerse
export type MishnahSeder={id:number;slug:string;title_he:string;title_en:string;order:number;tractate_count:number}
export type MishnahTractate={id:number;slug:string;title_he:string;title_en:string;order:number;chapter_count:number;source_name:string;license:string}
export type MishnahUnit={id:number;chapter:number;mishnah:number;text:string;ref:string}
export type TalmudTradition='bavli'|'yerushalmi'
export type TalmudTractate={id:number;tradition:TalmudTradition;seder_name:string;slug:string;title_he:string;title_en:string;order:number;section_count:number;source_name:string;source_url:string;license:string;license_verified:boolean}
export type TalmudSectionInfo={index:number;label:string;count:number}
export type TalmudSegment={id:number;section:number;position:number;path:string;text:string;ref:string}

const BASE=(import.meta.env.VITE_API_URL||(import.meta.env.PROD?'':'http://localhost:8000')).replace(/\/$/,'')
async function get<T>(path:string):Promise<T>{const r=await fetch(`${BASE}${path}`);if(!r.ok)throw new Error(await r.text());return r.json()}

export const api={
works:(q='',category='')=>get<Work[]>(`/api/v1/works${q||category?`?${[q&&`q=${encodeURIComponent(q)}`,category&&`category=${encodeURIComponent(category)}`].filter(Boolean).join('&')}`:''}`),
segments:(id:number,level1?:number)=>get<Segment[]>(`/api/v1/works/${id}/segments${level1?`?level1=${level1}`:''}`),
sections:(id:number)=>get<SectionInfo[]>(`/api/v1/works/${id}/sections`),
search:(q:string)=>get<SearchHit[]>(`/api/v1/search?q=${encodeURIComponent(q)}`),
categories:()=>get<CategoryStat[]>(`/api/v1/categories`),
stats:()=>get<Stats>(`/api/v1/stats`),
torahBooks:()=>get<TorahBook[]>(`/api/v1/torah/books`),
torahParashot:(slug:string)=>get<TorahParasha[]>(`/api/v1/torah/books/${slug}/parashot`),
torahChapter:(slug:string,chapter:number)=>get<TorahVerse[]>(`/api/v1/torah/books/${slug}/chapters/${chapter}`),
torahParashaChapter:(parashaId:number,chapter:number)=>get<TorahVerse[]>(`/api/v1/torah/parashot/${parashaId}/chapters/${chapter}`),
torahBookView:(slug:string)=>get<TorahVerse[]>(`/api/v1/torah/books/${slug}/book-view`),
neviimBooks:()=>get<NeviimBook[]>(`/api/v1/neviim/books`),
neviimChapter:(slug:string,chapter:number)=>get<NeviimVerse[]>(`/api/v1/neviim/books/${slug}/chapters/${chapter}`),
neviimBookView:(slug:string)=>get<NeviimVerse[]>(`/api/v1/neviim/books/${slug}/book-view`),
ketuvimBooks:()=>get<KetuvimBook[]>(`/api/v1/ketuvim/books`),
ketuvimChapter:(slug:string,chapter:number)=>get<KetuvimVerse[]>(`/api/v1/ketuvim/books/${slug}/chapters/${chapter}`),
ketuvimBookView:(slug:string)=>get<KetuvimVerse[]>(`/api/v1/ketuvim/books/${slug}/book-view`),
mishnahSedarim:()=>get<MishnahSeder[]>(`/api/v1/mishnah/sedarim`),
mishnahTractates:(sederSlug:string)=>get<MishnahTractate[]>(`/api/v1/mishnah/sedarim/${sederSlug}/tractates`),
mishnahChapter:(slug:string,chapter:number)=>get<MishnahUnit[]>(`/api/v1/mishnah/tractates/${slug}/chapters/${chapter}`),
mishnahTractateView:(slug:string)=>get<MishnahUnit[]>(`/api/v1/mishnah/tractates/${slug}/book-view`),
talmudTractates:(tradition:TalmudTradition)=>get<TalmudTractate[]>(`/api/v1/talmud/${tradition}/tractates`),
talmudSections:(tradition:TalmudTradition,slug:string)=>get<TalmudSectionInfo[]>(`/api/v1/talmud/${tradition}/tractates/${slug}/sections`),
talmudSection:(tradition:TalmudTradition,slug:string,section:number)=>get<TalmudSegment[]>(`/api/v1/talmud/${tradition}/tractates/${slug}/sections/${section}`),
talmudBookView:(tradition:TalmudTradition,slug:string)=>get<TalmudSegment[]>(`/api/v1/talmud/${tradition}/tractates/${slug}/book-view`)
}
