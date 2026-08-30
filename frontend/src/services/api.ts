export type Work={id:number;slug:string;title_he:string;title_en?:string;category:string;subcategory?:string;author?:string}
export type Segment={id:number;ref:string;section_title?:string;text:string}
export type SearchHit={work_id:number;work_title:string;ref:string;text:string}
const BASE=(import.meta.env.VITE_API_URL||'http://localhost:8000').replace(/\/$/,'')
async function get<T>(path:string):Promise<T>{const r=await fetch(`${BASE}${path}`);if(!r.ok)throw new Error(await r.text());return r.json()}
export const api={works:(q='')=>get<Work[]>(`/api/v1/works${q?`?q=${encodeURIComponent(q)}`:''}`),segments:(id:number)=>get<Segment[]>(`/api/v1/works/${id}/segments`),search:(q:string)=>get<SearchHit[]>(`/api/v1/search?q=${encodeURIComponent(q)}`),categories:()=>get<{name:string;count:number}[]>(`/api/v1/categories`)}
