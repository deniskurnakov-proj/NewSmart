const fs = require('fs');
const { chromium } = require('playwright');

const targets = [
  {key:'mark', name:'Отель Марк', url:'https://hotel-mark.ru/'},
  {key:'frog', name:'Princess Frog', url:'https://www.sbcomplex.su/'},
  {key:'dubna', name:'Гостиница Дубна', url:'https://hotel-dubna.ru/'},
  {key:'sadko', name:'Гостиница Садко', url:'https://www.sadko.com.ru/'},
  {key:'mityaevski', name:'Митяевский гостевой дом', url:'https://vk.com/mityaevski_guesthouse'}
];

const kw = /(номер|комнат|прожив|услуг|ресторан|кафе|банкет|свад|конферен|саун|спа|spa|бассейн|экскурс|отдых|акци|цены|тариф|booking|book|room|service|contact|about|контакт|о нас)/i;

function clean(s='') { return s.replace(/\u00a0/g,' ').replace(/[\t ]+/g,' ').replace(/\n{3,}/g,'\n\n').trim(); }
function uniq(a){ return [...new Set(a.filter(Boolean))]; }

async function extract(page, url) {
  const start = Date.now();
  let response = null;
  try {
    response = await page.goto(url, {waitUntil:'domcontentloaded', timeout:45000});
    await page.waitForTimeout(2500);
  } catch (e) {}
  const data = await page.evaluate(() => {
    const txt = (el) => (el?.innerText || el?.textContent || '').trim();
    const body = txt(document.body);
    const links = [...document.querySelectorAll('a[href]')].map(a => ({text:txt(a).replace(/\s+/g,' ').slice(0,180), href:a.href}));
    const h1 = [...document.querySelectorAll('h1')].map(txt).filter(Boolean);
    const h2 = [...document.querySelectorAll('h2')].map(txt).filter(Boolean);
    const buttons = [...document.querySelectorAll('button, a, [role="button"]')].map(txt).filter(Boolean).filter(x => x.length < 120);
    return {
      title: document.title,
      description: document.querySelector('meta[name="description"]')?.content || '',
      h1, h2, buttons,
      body,
      links,
      htmlLang: document.documentElement.lang || ''
    };
  }).catch(() => ({title:'',description:'',h1:[],h2:[],buttons:[],body:'',links:[],htmlLang:''}));
  const body = clean(data.body).slice(0,18000);
  const emails = uniq((body.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/ig) || []));
  const phones = uniq((body.match(/(?:\+7|8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-()]*\d{2}[\s\-()]*\d{2}/g) || []).map(x=>x.replace(/\s+/g,' ')));
  return {
    requestedUrl:url,
    finalUrl:page.url(),
    status:response?.status() || null,
    elapsedMs:Date.now()-start,
    title:clean(data.title),
    description:clean(data.description),
    h1:uniq(data.h1.map(clean)).slice(0,20),
    h2:uniq(data.h2.map(clean)).slice(0,40),
    buttons:uniq(data.buttons.map(clean)).slice(0,60),
    body,
    links:data.links,
    emails,
    phones
  };
}

(async()=>{
  const browser = await chromium.launch({headless:true});
  const context = await browser.newContext({
    viewport:{width:1440,height:1200},
    ignoreHTTPSErrors:true,
    locale:'ru-RU',
    userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/149 Safari/537.36'
  });
  const results=[];
  for (const t of targets) {
    const page = await context.newPage();
    const main = await extract(page,t.url);
    const origin = (()=>{try{return new URL(main.finalUrl||t.url).origin}catch{return ''}})();
    const candidates = main.links
      .filter(l=>{try{const u=new URL(l.href); return u.origin===origin && kw.test((l.text||'')+' '+u.pathname)}catch{return false}})
      .map(l=>l.href.split('#')[0]);
    const selected = uniq(candidates).filter(u=>u!==main.finalUrl).slice(0,8);
    const pages=[];
    for (const u of selected) {
      const p=await context.newPage();
      pages.push(await extract(p,u));
      await p.close();
    }
    results.push({...t, main, pages});
    await page.close();
    console.log('done',t.key,main.status,main.finalUrl,selected.length);
  }
  await browser.close();
  fs.mkdirSync('data',{recursive:true});
  fs.writeFileSync('data/personalize_leads.json',JSON.stringify({createdAt:new Date().toISOString(),results},null,2));

  const lines=[];
  for (const r of results) {
    lines.push(`# ${r.name}`);
    lines.push(`URL: ${r.main.finalUrl || r.url}`);
    lines.push(`HTTP: ${r.main.status}`);
    lines.push(`Title: ${r.main.title}`);
    lines.push(`Description: ${r.main.description}`);
    lines.push(`H1: ${r.main.h1.join(' | ')}`);
    lines.push(`H2: ${r.main.h2.join(' | ')}`);
    lines.push(`Buttons: ${r.main.buttons.join(' | ')}`);
    lines.push(`Emails: ${uniq([...(r.main.emails||[]),...r.pages.flatMap(p=>p.emails||[])]).join(' | ')}`);
    lines.push(`Phones: ${uniq([...(r.main.phones||[]),...r.pages.flatMap(p=>p.phones||[])]).join(' | ')}`);
    lines.push('Main text:');
    lines.push(r.main.body.slice(0,12000));
    for (const p of r.pages) {
      lines.push(`## Page ${p.finalUrl}`);
      lines.push(`Title: ${p.title}`);
      lines.push(`H1: ${p.h1.join(' | ')}`);
      lines.push(`H2: ${p.h2.join(' | ')}`);
      lines.push(p.body.slice(0,6000));
    }
    lines.push('');
  }
  fs.writeFileSync('data/personalize_leads.md',lines.join('\n'));
})().catch(e=>{console.error(e);process.exit(1)});
