import { Actor } from 'apify';
import { PuppeteerCrawler } from 'crawlee';

await Actor.init();

const CLUBS = [
    { name: "JS Kabylie",      sfId: 42202,  slug: "js-kabylie" },
    { name: "CR Belouizdad",   sfId: 42207,  slug: "cr-belouizdad" },
    { name: "MC Alger",        sfId: 42204,  slug: "mc-alger" },
    { name: "USM Alger",       sfId: 42206,  slug: "usm-alger" },
    { name: "CS Constantine",  sfId: 55393,  slug: "cs-constantine" },
    { name: "ES Setif",        sfId: 41756,  slug: "es-setif" },
    { name: "MC Oran",         sfId: 45001,  slug: "mc-oran" },
    { name: "ASO Chlef",       sfId: 42201,  slug: "aso-chlef" },
    { name: "JS Saoura",       sfId: 79565,  slug: "js-saoura" },
    { name: "ES Ben Aknoun",   sfId: 133444, slug: "es-ben-aknoun" },
    { name: "USM Khenchela",   sfId: 238384, slug: "usm-khenchela" },
    { name: "MB Rouissat",     sfId: 238383, slug: "mb-rouisset" },
    { name: "Paradou AC",      sfId: 212197, slug: "paradou-ac" },
    { name: "ES Mostaganem",   sfId: 186100, slug: "es-mostaganem" },
    { name: "MC El Bayadh",    sfId: 133466, slug: "mc-el-bayadh" },
    { name: "Olympique Akbou", sfId: 306567, slug: "olympique-akbou" },
];

const results = [];

const crawler = new PuppeteerCrawler({
    launchContext: {
        launchOptions: {
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        }
    },
    requestHandlerTimeoutSecs: 60,
    async requestHandler({ page, request }) {
        const club = request.userData.club;
        const apiUrl = `https://api.sofascore.com/api/v1/team/${club.sfId}/players`;
        
        const response = await page.evaluate(async (url) => {
            const res = await fetch(url, {
                headers: {
                    'Accept': 'application/json',
                    'Referer': 'https://www.sofascore.com/'
                }
            });
            return res.json();
        }, apiUrl);
        
        const players = response.players || [];
        console.log(`${club.name}: ${players.length} joueurs`);
        
        for (const item of players) {
            const p = item.player || item;
            if (!p.id) continue;
            
            let mv = null;
            if (p.proposedMarketValueRaw) mv = p.proposedMarketValueRaw.value;
            else if (p.proposedMarketValue) mv = p.proposedMarketValue;
            
            let contractUntil = null;
            if (p.contractUntilTimestamp) {
                contractUntil = new Date(p.contractUntilTimestamp * 1000).toISOString();
            }
            
            results.push({
                sofascore_id: p.id,
                name: p.name || '',
                short_name: p.shortName || '',
                slug: p.slug || '',
                team_name: club.name,
                sofascore_team_id: club.sfId,
                position: p.position || '',
                jersey_number: String(p.shirtNumber || p.jerseyNumber || ''),
                nationality: p.country?.name || '',
                market_value: mv,
                contract_until: contractUntil,
                photo_url: `https://api.sofascore.com/api/v1/player/${p.id}/image`,
            });
        }
    },
    failedRequestHandler({ request, error }) {
        console.error(`Erreur: ${error.message}`);
    }
});

const requests = CLUBS.map(club => ({
    url: `https://www.sofascore.com/team/football/${club.slug}/${club.sfId}`,
    userData: { club }
}));

await crawler.run(requests);
console.log(`Total: ${results.length} joueurs`);
await Actor.pushData(results);
await Actor.exit();