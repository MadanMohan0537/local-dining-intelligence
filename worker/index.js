const DEMO = [
  {name:'Harbor & Hearth',category:'New American',price_level:'$$$',rating:4.7,reviews_count:842,sentiment_score:.91,address:'12 Atlantic Ave, Boston, MA',latitude:42.3601,longitude:-71.0589},
  {name:'Spice Route Kitchen',category:'Indian',price_level:'$$',rating:4.6,reviews_count:618,sentiment_score:.88,address:'88 Cambridge St, Boston, MA',latitude:42.3618,longitude:-71.0575},
  {name:'North End Table',category:'Italian',price_level:'$$$',rating:4.4,reviews_count:1210,sentiment_score:.76,address:'41 Hanover St, Boston, MA',latitude:42.3637,longitude:-71.0542},
  {name:'Green Fork Cafe',category:'Vegan',price_level:'$$',rating:4.3,reviews_count:286,sentiment_score:.82,address:'205 Boylston St, Boston, MA',latitude:42.3519,longitude:-71.0701},
  {name:'Beacon Street Tacos',category:'Mexican',price_level:'$',rating:4.1,reviews_count:394,sentiment_score:.67,address:'720 Beacon St, Boston, MA',latitude:42.3495,longitude:-71.0991},
  {name:'Commonwealth Noodles',category:'Asian Fusion',price_level:'$$',rating:3.9,reviews_count:177,sentiment_score:.54,address:'9 Westland Ave, Boston, MA',latitude:42.3445,longitude:-71.0844}
]

function analytics(restaurants) {
  const rows = restaurants.map(r => {
    const rating = Number(r.rating) || 0, reviews = Number(r.reviews_count) || 0
    const sentiment = Number(r.sentiment_score ?? rating / 5)
    return {...r, intelligence_score: Math.round(100 * (.45 * rating / 5 + .40 * sentiment + .15 * Math.min(reviews, 500) / 500) * 10) / 10}
  }).sort((a,b)=>b.intelligence_score-a.intelligence_score)
  const grouped = {}
  for (const r of rows) {
    const key = r.category || 'Other'
    grouped[key] ||= {category:key,competitors:0,total_reviews:0,rating_sum:0}
    grouped[key].competitors++; grouped[key].total_reviews += Number(r.reviews_count)||0; grouped[key].rating_sum += Number(r.rating)||0
  }
  const maxReviews = Math.max(1,...Object.values(grouped).map(x=>x.total_reviews)), maxCompetitors=Math.max(1,...Object.values(grouped).map(x=>x.competitors))
  const opportunities=Object.values(grouped).map(x=>{const avg=x.rating_sum/x.competitors;return {...x,average_rating:Math.round(avg*100)/100,opportunity_score:Math.round(100*(.45*x.total_reviews/maxReviews+.35*(1-(x.competitors-1)/maxCompetitors)+.20*(1-avg/5))*10)/10}}).sort((a,b)=>b.opportunity_score-a.opportunity_score)
  return {location:'Boston, MA (Synthetic Demo)',restaurants:rows,opportunities,summary:{restaurants:rows.length,average_rating:Math.round(rows.reduce((s,x)=>s+Number(x.rating||0),0)/rows.length*100)/100,total_reviews:rows.reduce((s,x)=>s+Number(x.reviews_count||0),0),average_sentiment:Math.round(rows.reduce((s,x)=>s+Number(x.sentiment_score||0),0)/rows.length*100)/100,categories:Object.keys(grouped).length},disclaimer:'Synthetic demo data; not production market research.'}
}

function json(body,status=200){return new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'public, max-age=300','x-content-type-options':'nosniff'}})}
export default {async fetch(request,env){const url=new URL(request.url);if(url.pathname==='/health')return json({status:'ok',runtime:'cloudflare-workers'});if(url.pathname==='/api/demo')return json(analytics(DEMO));if(url.pathname.startsWith('/api/'))return json({error:'Not found'},404);return env.ASSETS.fetch(request)}}

