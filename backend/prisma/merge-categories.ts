/**
 * Merge categories from multiple sources into a single categories.json
 * Sources: existing categories.json, G2, Capterra, Product Hunt, LinkedIn V2
 *
 * Usage: npx tsx prisma/merge-categories.ts
 */
import { readFileSync, writeFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ─── Types ───────────────────────────────────────────────────────────────────
interface CategoryEntry {
  name: string;
  description: string;
  children: string[];
}

interface G2Group {
  name: string;
  categories: { name: string; children: string[] }[];
}

interface CapterraData {
  popularByGroup: Record<string, { name: string; href: string }[]>;
  allCategories: { name: string; slug: string }[];
}

interface PHEntry {
  name: string;
  slug: string;
  children?: { name: string; slug: string }[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function clean(name: string): string {
  return name
    .replace(/\?.*$/, '')           // strip URL query params like ?ref=footer
    .replace(/\s+Software$/i, '')
    .replace(/\s+Tools?$/i, '')
    .replace(/\s+Platforms?$/i, '')
    .replace(/\s+Solutions?$/i, '')
    .replace(/\s+Systems?$/i, '')
    .replace(/\s+Services?$/i, '')
    .replace(/\s+Providers?$/i, '')
    .trim();
}

function normalize(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, '');
}

/** Deduplicated add: skip if a normalized version already exists */
function addUnique(arr: string[], items: string[], existingNorms: Set<string>) {
  for (const item of items) {
    const norm = normalize(item);
    if (norm.length < 2) continue;
    if (existingNorms.has(norm)) continue;
    existingNorms.add(norm);
    arr.push(item);
  }
}

// ─── Load sources ────────────────────────────────────────────────────────────
const existing: CategoryEntry[] = JSON.parse(
  readFileSync(resolve(__dirname, 'categories.json'), 'utf-8'),
);

const g2: G2Group[] = JSON.parse(
  readFileSync(resolve(process.env.HOME!, 'Downloads/g2-categories-full.json'), 'utf-8'),
);

const capterra: CapterraData = JSON.parse(
  readFileSync(resolve(process.env.HOME!, 'Downloads/capterra-categories.json'), 'utf-8'),
);

const ph: PHEntry[] = JSON.parse(
  readFileSync(resolve(process.env.HOME!, 'Downloads/producthunt-categories.json'), 'utf-8'),
);

// ─── LinkedIn V2 (manually compiled from our research) ───────────────────────
const linkedinV2: Record<string, string[]> = {
  'Accommodation & Hospitality': [
    'Hotels & Motels', 'Bed-and-Breakfasts & Hostels', 'Bars & Nightclubs',
    'Caterers', 'Mobile Food Services', 'Restaurants',
  ],
  'Administrative & Support Services': [
    'Collection Agencies', 'Events Services', 'Facilities Services',
    'Janitorial Services', 'Landscaping Services', 'Fundraising',
    'Office Administration', 'Security & Investigations',
    'Security Guards & Patrol', 'Staffing & Recruiting',
    'Executive Search', 'Telephone Call Centers',
    'Translation & Localization', 'Travel Arrangements',
  ],
  'Construction': [
    'Building Construction', 'Nonresidential Building', 'Residential Building',
    'Civil Engineering', 'Highway & Bridge Construction',
    'Utility System Construction', 'Building Equipment Contractors',
    'Building Finishing Contractors', 'Building Structure & Exterior',
  ],
  'Consumer Services': [
    'Civic & Social Organizations', 'Industry Associations',
    'Professional Organizations', 'Household Services',
    'Personal Care Services', 'Pet Services',
    'Laundry & Drycleaning', 'Religious Institutions',
    'Vehicle Repair & Maintenance',
  ],
  'Education': [
    'E-Learning Providers', 'Higher Education',
    'Primary & Secondary Education', 'Professional Training & Coaching',
    'Technical & Vocational Training', 'Language Schools',
    'Sports & Recreation Instruction', 'Flight Training',
  ],
  'Entertainment': [
    'Artists & Writers', 'Museums & Historical Sites', 'Zoos & Botanical Gardens',
    'Musicians', 'Performing Arts', 'Spectator Sports',
    'Dance Companies', 'Theater Companies',
    'Amusement Parks & Arcades', 'Gambling & Casinos',
    'Golf Courses & Country Clubs', 'Skiing Facilities',
    'Wellness & Fitness Services',
  ],
  'Farming, Ranching & Forestry': [
    'Farming', 'Horticulture', 'Forestry & Logging',
    'Fisheries', 'Ranching',
  ],
  'Financial Services': [
    'Capital Markets', 'Investment Advice', 'Investment Banking',
    'Investment Management', 'Securities & Commodity Exchanges',
    'Venture Capital & Private Equity', 'Banking',
    'International Trade & Development', 'Loan Brokers',
    'Insurance', 'Insurance Agencies & Brokerages',
    'Pension Funds', 'Trusts & Estates',
  ],
  'Government & Public Administration': [
    'Correctional Institutions', 'Courts of Law', 'Fire Protection',
    'Law Enforcement', 'Public Safety', 'Transportation Programs',
    'Utilities Administration', 'Environmental Programs',
    'Public Health', 'Education Administration',
    'Housing & Community Development', 'Armed Forces',
    'International Affairs', 'Space Research & Technology',
  ],
  'Hospitals & Health Care': [
    'Community Services', 'Services for Elderly & Disabled',
    'Hospitals', 'Child Day Care', 'Emergency & Relief Services',
    'Alternative Medicine', 'Ambulance Services', 'Chiropractors',
    'Dentists', 'Home Health Care', 'Medical Laboratories',
    'Mental Health Care', 'Optometrists', 'Physicians',
    'Physical & Occupational Therapists', 'Nursing Homes',
    'Veterinary',
  ],
  'Manufacturing': [
    'Apparel Manufacturing', 'Appliances & Electronics Manufacturing',
    'Chemical Manufacturing', 'Pharmaceutical Manufacturing',
    'Computer Hardware Manufacturing', 'Semiconductor Manufacturing',
    'Food & Beverage Manufacturing', 'Furniture Manufacturing',
    'Glass & Ceramics Manufacturing', 'Machinery Manufacturing',
    'Medical Equipment Manufacturing', 'Plastics & Rubber Manufacturing',
    'Paper & Forest Products', 'Textiles', 'Automotive Manufacturing',
    'Transportation Equipment Manufacturing',
  ],
  'Mining, Oil & Gas': [
    'Coal Mining', 'Metal Ore Mining', 'Nonmetallic Mineral Mining',
    'Natural Gas Extraction', 'Oil Extraction',
  ],
  'Professional Services': [
    'Accounting', 'Advertising & PR', 'Architecture & Planning',
    'Business Consulting', 'Design Services', 'Graphic Design',
    'Interior Design', 'Engineering Services',
    'Legal Services', 'IT Consulting',
    'Research & Development', 'Veterinary Services',
    'Market Research', 'Photography', 'Management Consulting',
  ],
  'Real Estate': [
    'Commercial & Industrial Equipment Rental',
    'Leasing Non-residential Real Estate',
    'Leasing Residential Real Estate',
    'Real Estate Agents & Brokers',
  ],
  'Retail': [
    'Online & Mail Order Retail', 'Retail Apparel & Fashion',
    'Retail Electronics', 'Retail Books',
    'Retail Building Materials', 'Retail Furniture',
    'Retail Health & Personal Care', 'Retail Pharmacies',
    'Retail Luxury Goods & Jewelry', 'Retail Motor Vehicles',
    'Retail Groceries', 'Retail Office Supplies',
  ],
  'Technology, Information & Media': [
    'Business Intelligence Platforms', 'Blockchain Services',
    'Internet Publishing', 'Online Audio & Video Media',
    'Internet Marketplace Platforms', 'Social Networking Platforms',
    'Software Development', 'Computer Games',
    'Data Security Products', 'Mobile Computing Software',
    'Book Publishing', 'Newspaper Publishing',
    'Radio & Television Broadcasting',
    'Telecommunications', 'Wireless Services',
  ],
  'Transportation & Logistics': [
    'Airlines & Aviation', 'Freight & Package Transportation',
    'Ground Passenger Transportation', 'Maritime Transportation',
    'Pipeline Transportation', 'Postal Services',
    'Rail Transportation', 'Truck Transportation',
    'Warehousing & Storage',
  ],
  'Utilities': [
    'Electric Power Generation', 'Nuclear Electric Power',
    'Renewable Energy Power Generation', 'Solar Electric Power',
    'Wind Electric Power', 'Hydroelectric Power',
    'Natural Gas Distribution', 'Water Supply & Irrigation',
    'Waste Collection', 'Waste Treatment & Disposal',
  ],
  'Wholesale': [
    'Wholesale Computer Equipment', 'Wholesale Electronics',
    'Wholesale Building Materials', 'Wholesale Food & Beverage',
    'Wholesale Machinery', 'Wholesale Metals & Minerals',
    'Wholesale Chemical Products', 'Wholesale Petroleum',
    'Wholesale Apparel', 'Wholesale Import & Export',
  ],
};

// ─── Mapping: G2 group name → our parent name ──────────────────────────────
const g2GroupMapping: Record<string, string> = {
  'Artificial Intelligence Software': 'AI & Machine Learning',
  'Analytics Tools & Software': 'Data & Analytics',
  'CAD & PLM Software': 'Manufacturing & Industrial',
  'Collaboration & Productivity Software': 'Project & Work Management',
  'Commerce Software': 'E-Commerce',
  'Content Management Systems': 'Content & Media',
  'Customer Service Software': 'Customer Support',
  'Data Privacy Software': 'Data & Analytics',
  'Design Software': 'Design & Creative Tools',
  'Development Software': 'Developer Tools',
  'Digital Advertising Tech': 'Marketing Technology',
  'ERP Software': 'Business Operations',
  'Governance, Risk & Compliance Software': 'Governance, Risk & Compliance (GRC)',
  'Hosting Providers': 'IT Management',
  'HR Software': 'HR & People',
  'IoT Management Platforms': 'Telecom & Connectivity',
  'IT Infrastructure Software': 'IT Management',
  'IT Management Software': 'IT Management',
  'Marketing Software': 'Marketing Technology',
  'Office Management Software': 'Business Operations',
  'Security Software': 'Cybersecurity',
  'Supply Chain & Logistics Software': 'Logistics & Supply Chain',
  // G2 groups that become NEW parents
  'AR/VR Software': 'AR/VR & Spatial Computing',
  'B2B Marketplaces': 'B2B Marketplaces',
  'Business Services Providers': 'Professional Services',
  'Ecosystem Service Providers': 'Professional Services',
  'Greentech Providers': 'Energy & CleanTech',
  'Marketplace Apps': 'E-Commerce',
  'Other Services Providers': 'Professional Services',
  'Professional Services Providers': 'Professional Services',
  'Sales Tools': 'Sales & Revenue',
  'Marketing Services Providers': 'Marketing Technology',
  'Security and Privacy Services Providers': 'Cybersecurity',
  'Staffing Services Providers': 'Recruiting & Talent',
  // 'Vertical Industry Software' — redistribute children via keyword matching below
  // Hardware groups - create hardware parent
  'Routers Hardware': 'Hardware & Networking',
  'Security Hardware': 'Hardware & Networking',
  'Servers Hardware': 'Hardware & Networking',
  'Storage Hardware': 'Hardware & Networking',
};

// Mapping: Capterra group → our parent
const capterraGroupMapping: Record<string, string> = {
  'Human Resources': 'HR & People',
  'Product Management & Productivity': 'Project & Work Management',
  'Marketing & Sales': 'Marketing Technology',
  'Operations and Resource Management': 'Business Operations',
  'Service Software': 'Professional Services',
  'IT & Security': 'IT Management',
  'Finance & Accounting': 'Accounting & Finance Ops',
  'Legal & Compliance': 'Legal Tech',
  'Customer Service & Support': 'Customer Support',
  'Hospitality': 'Travel & Hospitality',
  'Healthcare': 'HealthTech',
};

// Mapping: LinkedIn V2 group → our parent
const linkedinMapping: Record<string, string> = {
  'Accommodation & Hospitality': 'Travel & Hospitality',
  'Administrative & Support Services': 'Business Operations',
  'Construction': 'Construction & Architecture',
  'Consumer Services': 'Consumer Services',
  'Education': 'EdTech',
  'Entertainment': 'Media & Entertainment',
  'Farming, Ranching & Forestry': 'Agriculture & AgTech',
  'Financial Services': 'FinTech & Banking',
  'Government & Public Administration': 'GovTech',
  'Hospitals & Health Care': 'HealthTech',
  'Manufacturing': 'Manufacturing & Industrial',
  'Mining, Oil & Gas': 'Mining, Oil & Gas',
  'Professional Services': 'Professional Services',
  'Real Estate': 'PropTech',
  'Retail': 'Retail Tech',
  'Technology, Information & Media': 'Technology & Media',
  'Transportation & Logistics': 'Logistics & Supply Chain',
  'Utilities': 'Energy & CleanTech',
  'Wholesale': 'Wholesale & Distribution',
};

// ─── Build the merged taxonomy ───────────────────────────────────────────────
// Start with existing categories as the base
const merged = new Map<string, { description: string; children: string[]; childNorms: Set<string> }>();

for (const cat of existing) {
  const childNorms = new Set(cat.children.map(normalize));
  merged.set(cat.name, { description: cat.description, children: [...cat.children], childNorms });
}

function ensureParent(name: string, description: string) {
  if (!merged.has(name)) {
    merged.set(name, { description, children: [], childNorms: new Set() });
  }
}

function addChildren(parentName: string, children: string[]) {
  const parent = merged.get(parentName);
  if (!parent) return;
  addUnique(parent.children, children, parent.childNorms);
}

const unmatched: string[] = [];

// ─── Merge G2 ────────────────────────────────────────────────────────────────
for (const group of g2) {
  const parentName = g2GroupMapping[group.name];
  if (!parentName) continue;

  ensureParent(parentName, `${group.name} (from G2)`);

  const childNames: string[] = [];
  for (const cat of group.categories) {
    const cleaned = clean(cat.name);
    if (cleaned.length > 2) childNames.push(cleaned);
    // G2 sub-categories become children too (flattened to 2 levels)
    for (const sub of cat.children) {
      const cleanedSub = clean(sub);
      if (cleanedSub.length > 2) childNames.push(cleanedSub);
    }
  }

  addChildren(parentName, childNames);
}

// ─── Merge Capterra ──────────────────────────────────────────────────────────
// Use group mappings for the popular categories
for (const [group, cats] of Object.entries(capterra.popularByGroup)) {
  const parentName = capterraGroupMapping[group];
  if (!parentName) continue;
  addChildren(parentName, cats.map(c => clean(c.name)));
}

// All categories (flat) — assign by keyword matching
// NOTE: No trailing \b — allows prefix matching (e.g. "account" matches "Accounting")
// Order matters: more specific patterns first, broader last
const keywordToParent: [RegExp, string][] = [
  // ── Vertical industries (specific first) ──
  [/\b(church|faith|religious|worship|ministry|tithe|synagogue|mosque|congregation)/i, 'Non-Profit & Social Impact'],
  [/\b(nonprofit|non-profit|donor|fundrais|volunteer|grant manage|philanthrop|ngo|advocacy|petition|social work)/i, 'Non-Profit & Social Impact'],
  [/\b(veterinar|animal shelter|pet |kennel|grooming|zoo\b)/i, 'HealthTech'],
  [/\b(dental|dentist|orthodon)/i, 'HealthTech'],
  [/\b(mental health|behavioral health|therap|counseling|psych|speech therap)/i, 'HealthTech'],
  [/\b(health|medical|clinical|patient|ehr|emr|telemedicine|telehealth|pharma|nursing|hospital|ambulat|ambulance|chiropr|optometr|physician|radiol|oncol|cardiol|lab info|e-?prescri|assisted living|home care|hospice|vaccine|blood bank)/i, 'HealthTech'],
  [/\b(gym|fitness|wellness|yoga|meditation|nutrition|diet|sleep|wearable|swim club)/i, 'Wellness & Fitness'],
  [/\b(restaurant|food service|recipe|kitchen|menu|catering|bakery|barber|salon|spa\b|beauty|tattoo|tanning)/i, 'Food & Restaurant Tech'],
  [/\b(hotel|hospitality|travel|tour operator|vacation rental|resort|lodging|concierge|timeshare)/i, 'Travel & Hospitality'],
  [/\b(auto repair|auto shop|auto dealer|car dealer|vehicle inspect|dealer manage|tire\b|collision|oil change|tow)/i, 'Automotive'],
  [/\b(auto\b|automobile|vehicle|fleet electr|ev charg|connected car|mobility|taxi|limousine)/i, 'Automotive'],
  [/\b(farm|agricult|crop|livestock|soil|irrigation|harvest|dairy|ranch|fish|aquaculture|viticulture|wine|vineyard|brewery|distill|seed to sale)/i, 'Agriculture & AgTech'],
  [/\b(cannabis|marijuana|dispensary|hemp)/i, 'Agriculture & AgTech'],
  [/\b(real estate|property manag|tenant|lease manag|mortgage|mls\b|appraisal|escrow|title prod|home inspector|apartment|self.storage|condo)/i, 'PropTech'],
  [/\b(construction|contractor|subcontract|estimat|takeoff\b|bim\b|blueprint|lien\b|punch list|jobsite|excavat|paving|roofing|plumb|electric)/i, 'Construction & Architecture'],
  [/\b(architect|interior design|landscape design|land survey|building design)/i, 'Construction & Architecture'],
  [/\b(insurance|insur|underwrite|policy admin|actuari|claim adjust)/i, 'InsurTech'],
  [/\b(govern|civic|public sector|permit|emergency manage|election|voting|municipal|county|city manage|code enforce|public works|smart cit)/i, 'GovTech'],
  [/\b(law practice|law firm|legal case|legal billing|legal calen|court\b|litigation|e-?discovery|deposition|paralegal|trust account)/i, 'Legal Tech'],
  [/\b(legal|compliance|contract manage|contract lifecycle|gdpr|ccpa|patent|trademark|ip manage|regulatory|whistleblow)/i, 'Legal Tech'],
  [/\b(camp manage|summer camp|recreation manage|parks\b)/i, 'EdTech'],
  [/\b(child care|day care|preschool|k-12|higher ed|university|college|academic|student|classroom|school|tutor|scholarship|special education|eLearning auth)/i, 'EdTech'],
  [/\b(learn|lms\b|elearn|e-learn|course\b|training|education|literacy|assessment|proctoring|credential|admissions)/i, 'EdTech'],
  [/\b(mining|oil\b|gas\b|petroleum|drill|refin|quarry|mineral)/i, 'Mining, Oil & Gas'],
  [/\b(aerospace|aviation|airline|flight|air cargo|airport)/i, 'Logistics & Supply Chain'],

  // ── Tech-specific ──
  [/\b(ai |artificial intelligence|machine learn|nlp\b|chatbot|llm\b|deep learn|neural|computer vision|ai agent|ai assist|ai writ|ai avatar|ai voice|ai grad|ai orchestrat|ai note|ai legal|ai medical|text.to.speech|speech recogn|text.to.image)/i, 'AI & Machine Learning'],
  [/\b(security|firewall|antivirus|endpoint protect|identity.*manage|access manage|threat|vulnerabil|password|encrypt|siem\b|soar\b|pentest|phishing|malware|ransomware|zero trust|sase\b|authenticat|mfa\b|2fa\b|sso\b|bot detect|xdr\b|vpn\b|anti-spam)/i, 'Cybersecurity'],
  [/\b(develop|api |api-|code review|devops|ci.cd|github|test manage|debug|sdk\b|ide\b|version control|git\b|docker|kubernetes|terraform|deploy|staging|microservice|serverless|webhook|source code|app build|application develop|application lifecycle|low.code|no.code|vibe cod|static site)/i, 'Developer Tools'],
  [/\b(cloud|server\b|infrastructure|network monitor|backup|disaster recov|it service|itsm\b|cmdb\b|asset manage|license manage|endpoint manage|mdm\b|uem\b|apm\b|observab|aiops|it manage|virtual machine|virtualiz|vdi\b|web.*monitor|website monitor)/i, 'IT Management'],
  [/\b(data |analytics|business intelligence|big data|dashboard|visualiz|warehouse|etl\b|data integrat|data catalog|data govern|data quality|data pipeline|statistic|text mining|web scrap|spread)/i, 'Data & Analytics'],
  [/\b(web3|nft\b|dao\b|decentral|token\b|smart contract|blockchain|crypto|defi\b|wallet\b)/i, 'Web3 & Blockchain'],
  [/\b(ar\b|vr\b|augmented reality|virtual reality|spatial|mixed reality|3d print|additive manufact|drone|uav\b|quantum|wearable comput)/i, 'Emerging Tech'],
  [/\b(telecom|voip|sip\b|pbx\b|iot |connectiv|5g\b|sd-wan|unified comm|ucaas|cpaas|softphone|telephon)/i, 'Telecom & Connectivity'],

  // ── Business functions ──
  [/\b(hr\b|human resource|employee|payroll|workforce|talent manage|recruit|hiring|onboard|offboard|applicant track|performance manage|absence|attendance|time track|time clock|time.?sheet|compensation|benefit admin|dei\b|background check|staffing|360 degree|succession|job board)/i, 'HR & People'],
  [/\b(market|seo\b|email market|advertis|campaign|social media|influenc|brand manage|content market|affiliate|referral|lead scor|conversion|retarget|programmatic|media buy|pr\b|public relation|app store optim|social listen|social sell|telemarket)/i, 'Marketing Technology'],
  [/\b(sale|crm\b|lead gen|prospect|revenue|deal\b|pipeline|quota|territory|sales engag|sales enabl|sales coach|outbound|cold email|sales intel|sales forecast|sales force|sales track|sales perform|sales tax)/i, 'Sales & Revenue'],
  [/\b(account|bookkeep|tax\b|invoice|billing|financ|budget|expense|payable|receivable|audit|treasury|procurement|purchas|spend manage|corporate card|fp.a|financial close|general ledger|brokerage|stock portfolio|venture capital)/i, 'Accounting & Finance Ops'],
  [/\b(project manage|task manage|collaborat|agile\b|scrum\b|kanban|sprint|gantt|okr\b|goal set|work manage|issue track|resource plan|capacity plan|portfolio manage|program manage|product manage|whiteboard|note.tak|wiki\b|knowledge manage|strategic plan|team manage)/i, 'Project & Work Management'],
  [/\b(customer service|help desk|ticket|live chat|call center|contact center|customer feedback|nps\b|omnichannel|knowledge base|self.service|service desk|complaint)/i, 'Customer Support'],
  [/\b(customer success|churn|retention|digital adopt|user engag|health scor|renewal)/i, 'Customer Success'],
  [/\b(ecommerce|e-commerce|shopping cart|storefront|marketplace|point of sale|pos\b|order manage|fulfillment|drop.?ship|subscription manage|product inform|product catalog|pricing\b|coupon|discount|gift card|bar pos|ipad pos)/i, 'E-Commerce'],
  [/\b(payment|gateway|fintech|banking|lending|loan\b|credit\b|neobank|remittance|money transfer|dunning|chargeback|collections\b)/i, 'FinTech & Banking'],
  [/\b(erp\b|enterprise resource|workflow|document manage|process auto|bpm\b|digital form|e-?signature|digital signature|integrat|ipaas|rpa\b|robotic process|office manage|visitor manage|print manage|mail manage|schedul|appointment|booking engine|calendar|dispatch|archiv|barcode|kiosk|waiver|waitlist)/i, 'Business Operations'],
  [/\b(logistics|supply chain|shipping|freight|warehouse manage|wms\b|fleet manage|transport manage|tms\b|route optim|last.mile|demand plan|carrier|yard manage|terminal operat|trucking|shipment track|vessel track|postal)/i, 'Logistics & Supply Chain'],
  [/\b(manufactur|quality manage|shop floor|inventor|plm\b|cad\b|cmms|maintenance\b|mes\b|mrp\b|bill of material|production plan|work order|tool manage|3d cad|warranty)/i, 'Manufacturing & Industrial'],
  [/\b(energy|solar|wind|carbon|sustain|cleantech|renewable|utility|smart grid|emission|esg\b|water manage|waste manage|wastewater)/i, 'Energy & CleanTech'],
  [/\b(design|ui.ux|prototype|wireframe|graphic|creative|figma|sketch|adobe|illustrat|3d render|3d model|3d architec|animation|motion graphic|brand identity|logo\b|diagram|font |vector|photo.*edit|user experience)/i, 'Design & Creative Tools'],
  [/\b(cms\b|content manage|blog\b|publish|video edit|video mak|podcast|photo manage|writing|screen.?writ|translat|localiz|dam\b|digital asset|media manage|video host|url short)/i, 'Content & Media'],
  [/\b(video conferenc|video call|video interview|messag|communicat|email\b|intranet|enterprise social|webinar|virtual event|screen shar|remote desktop|team chat|web conferenc|audio conferenc|screen record)/i, 'Communication & Collaboration'],
  [/\b(risk manage|audit manage|grc\b|governance|internal audit|policy manage|business continu|whistleblow)/i, 'Governance, Risk & Compliance (GRC)'],
  [/\b(creator|newsletter|membership|fan engag|freelanc|link.in.bio|patron|merch\b)/i, 'Creator Economy'],
  [/\b(game|gaming|esport|stream|entertainment|music|audio\b|video stream|ott\b|sport|event\b|ticket|venue|theatre|theater|amusement|simulat)/i, 'Media & Entertainment'],

  // ── Broad fallback patterns ──
  [/\b(retail|store\b|shop\b|merchandis|loyalty|reward)/i, 'Retail Tech'],
  [/\b(distribut|wholesale|import|export|trade\b)/i, 'Wholesale & Distribution'],
  [/\b(consult|advisory|profession|agency\b|coach\b|mentor|studio manage|photography)/i, 'Professional Services'],
  [/\b(survey|quiz|poll|feedback|review\b|form\b|sign\b)/i, 'Business Operations'],
  [/\b(report|kpi\b|metric|benchmark)/i, 'Data & Analytics'],
  [/\b(chat\b|sms\b|notification|alert\b)/i, 'Communication & Collaboration'],
  [/\b(optim|automat)/i, 'Business Operations'],
  [/\b(manage|track|monitor|platform|system)/i, 'Business Operations'],
];

for (const cat of capterra.allCategories) {
  const name = clean(cat.name);
  if (name.length < 3) continue;

  let assigned = false;
  for (const [re, parent] of keywordToParent) {
    if (re.test(name)) {
      ensureParent(parent, '');
      addChildren(parent, [name]);
      assigned = true;
      break;
    }
  }
  if (!assigned) {
    unmatched.push(name);
  }
}

// ─── Merge Product Hunt ──────────────────────────────────────────────────────
for (const entry of ph) {
  const name = entry.name;
  if (!name || name.length < 3) continue;

  let assigned = false;
  for (const [re, parent] of keywordToParent) {
    if (re.test(name)) {
      ensureParent(parent, '');
      addChildren(parent, [name]);
      assigned = true;
      break;
    }
  }
  if (!assigned) {
    unmatched.push(name);
  }

  // Also add children if present
  if (entry.children) {
    for (const child of entry.children) {
      if (child.name && child.name.length > 2) {
        let childAssigned = false;
        for (const [re, parent] of keywordToParent) {
          if (re.test(child.name)) {
            ensureParent(parent, '');
            addChildren(parent, [child.name]);
            childAssigned = true;
            break;
          }
        }
        if (!childAssigned) unmatched.push(child.name);
      }
    }
  }
}

// ─── Redistribute G2 "Vertical Industry Software" via keyword matching ───────
const verticalGroup = g2.find(g => g.name === 'Vertical Industry Software');
if (verticalGroup) {
  for (const cat of verticalGroup.categories) {
    const items = [clean(cat.name), ...cat.children.map(clean)].filter(n => n.length > 2);
    for (const name of items) {
      let assigned = false;
      for (const [re, parent] of keywordToParent) {
        if (re.test(name)) {
          ensureParent(parent, '');
          addChildren(parent, [name]);
          assigned = true;
          break;
        }
      }
      if (!assigned) unmatched.push(name);
    }
  }
}

// ─── Merge LinkedIn V2 ──────────────────────────────────────────────────────
for (const [group, children] of Object.entries(linkedinV2)) {
  const parentName = linkedinMapping[group] || group;
  ensureParent(parentName, `${group} (from LinkedIn V2)`);
  addChildren(parentName, children);
}

// ─── Output ──────────────────────────────────────────────────────────────────
// ─── Dedup pass: merge near-duplicate children within each parent ─────────────
function dedupeKey(name: string): string {
  return name
    .toLowerCase()
    .replace(/\?.*$/, '')                    // strip URL params
    .replace(/\b(software|tools?|platforms?|solutions?|systems?|services?|providers?)\b/g, '')
    .replace(/[^a-z0-9]/g, '')
    .replace(/(ors?|ers?|s|ing|tion|ment)$/, ''); // strip trailing suffixes
}

for (const [, data] of merged) {
  const seen = new Map<string, string>();    // dedupeKey → best name
  const deduped: string[] = [];

  for (const child of data.children) {
    const key = dedupeKey(child);
    if (key.length < 2) continue;

    if (seen.has(key)) {
      // Keep the longer/more descriptive name
      const existing = seen.get(key)!;
      if (child.length > existing.length && !child.includes('?')) {
        // Replace with better name
        const idx = deduped.indexOf(existing);
        if (idx !== -1) deduped[idx] = child;
        seen.set(key, child);
      }
    } else {
      seen.set(key, child);
      deduped.push(child);
    }
  }

  data.children = deduped;
  data.childNorms = new Set(deduped.map(normalize));
}

// Sort children alphabetically, build final structure
const output: CategoryEntry[] = [];

for (const [name, data] of merged) {
  if (data.children.length === 0) continue; // skip empty parents
  if (name === 'Other Software & Services' || name === 'Industry-Specific Software') continue; // skip catch-alls
  output.push({
    name,
    description: data.description,
    children: data.children.sort((a, b) => a.localeCompare(b)),
  });
}

// Sort parents alphabetically
output.sort((a, b) => a.name.localeCompare(b.name));

// Stats
let totalChildren = 0;
for (const cat of output) totalChildren += cat.children.length;

// Deduplicate unmatched
const uniqueUnmatched = [...new Set(unmatched)].sort();

console.log(`\nMerged taxonomy: ${output.length} parents, ${totalChildren} sub-niches (${output.length + totalChildren} total)\n`);

// Top 10 largest
const sorted = [...output].sort((a, b) => b.children.length - a.children.length);
console.log('Top 10 largest groups:');
for (const cat of sorted.slice(0, 10)) {
  console.log(`  ${cat.name}: ${cat.children.length}`);
}

console.log(`\nUnmatched items (dropped): ${uniqueUnmatched.length}`);
if (uniqueUnmatched.length > 0) {
  console.log('Sample:', uniqueUnmatched.slice(0, 20).join(', '));
}

// Write
const outPath = resolve(__dirname, 'categories.json');
writeFileSync(outPath, JSON.stringify(output, null, 2) + '\n');
console.log(`\nWritten to ${outPath}`);
