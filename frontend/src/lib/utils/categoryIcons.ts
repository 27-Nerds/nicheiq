/**
 * Phase 5.4 — slug → lucide icon component mapping for category badges in the
 * public catalog. Hardcoded per scope decision (DB column deferred). When a
 * slug isn't matched, the default Layers icon renders.
 *
 * Add new mappings here as needed; the icon name should be a lowercase
 * descriptor that matches the visual concept of the niche.
 */

import Layers from "lucide-svelte/icons/layers";
import Cloud from "lucide-svelte/icons/cloud";
import Wallet from "lucide-svelte/icons/wallet";
import Heart from "lucide-svelte/icons/heart";
import Megaphone from "lucide-svelte/icons/megaphone";
import Factory from "lucide-svelte/icons/factory";
import Landmark from "lucide-svelte/icons/landmark";
import ShoppingBag from "lucide-svelte/icons/shopping-bag";
import GraduationCap from "lucide-svelte/icons/graduation-cap";
import Stethoscope from "lucide-svelte/icons/stethoscope";
import Briefcase from "lucide-svelte/icons/briefcase";
import Cpu from "lucide-svelte/icons/cpu";
import Sparkles from "lucide-svelte/icons/sparkles";
import Code from "lucide-svelte/icons/code";
import Plane from "lucide-svelte/icons/plane";
import UtensilsCrossed from "lucide-svelte/icons/utensils-crossed";
import Home from "lucide-svelte/icons/home";
import Truck from "lucide-svelte/icons/truck";
import Leaf from "lucide-svelte/icons/leaf";
import Music from "lucide-svelte/icons/music";
import Calculator from "lucide-svelte/icons/calculator";
import Tractor from "lucide-svelte/icons/tractor";
import Glasses from "lucide-svelte/icons/glasses";
import Car from "lucide-svelte/icons/car";
import ClipboardList from "lucide-svelte/icons/clipboard-list";
import MessagesSquare from "lucide-svelte/icons/messages-square";
import Clapperboard from "lucide-svelte/icons/clapperboard";
import UserCheck from "lucide-svelte/icons/user-check";
import Headset from "lucide-svelte/icons/headset";
import Shield from "lucide-svelte/icons/shield";
import ChartNoAxesCombined from "lucide-svelte/icons/chart-no-axes-combined";
import ShoppingCart from "lucide-svelte/icons/shopping-cart";
import Atom from "lucide-svelte/icons/atom";
import Server from "lucide-svelte/icons/server";
import Umbrella from "lucide-svelte/icons/umbrella";
import MonitorCog from "lucide-svelte/icons/monitor-cog";
import Fuel from "lucide-svelte/icons/fuel";
import HeartHandshake from "lucide-svelte/icons/heart-handshake";
import Handshake from "lucide-svelte/icons/handshake";
import ListChecks from "lucide-svelte/icons/list-checks";
import RadioTower from "lucide-svelte/icons/radio-tower";
import Boxes from "lucide-svelte/icons/boxes";
import Warehouse from "lucide-svelte/icons/warehouse";

import type { ComponentType } from "svelte";

// Rules are checked in order; first match wins. Specific multi-word slugs go
// before the broad concept-family rules so e.g. "customer-success" doesn't
// fall through to Layers. Patterns are matched against REAL hyphenated DB
// slugs — when adding a category, test the actual slug, not the display name.
const SLUG_RULES: Array<[RegExp, ComponentType]> = [
  // Specific top-level category slugs (audited against the live catalog).
  [/^accounting/, Calculator],
  [/^(agriculture|agtech|farming)/, Tractor],
  [/^(ar-vr|vr-|xr-|spatial)/, Glasses],
  [/^(automotive|auto-)/, Car],
  [/^business-operations/, ClipboardList],
  [/^(communication|collaboration)/, MessagesSquare],
  [/^creator/, Clapperboard],
  [/^customer-success/, UserCheck],
  [/^customer-support/, Headset],
  [/^(cybersecurity|security)/, Shield],
  [/^(data-analytics|data-|analytics)/, ChartNoAxesCombined],
  [/^(e-commerce|ecommerce)/, ShoppingCart],
  [/^emerging/, Atom],
  [/^(hardware|networking)/, Server],
  [/^(insurtech|insurance)/, Umbrella],
  [/^it-management/, MonitorCog],
  [/^(mining|oil|gas)/, Fuel],
  [/^(non-profit|nonprofit|social-impact)/, HeartHandshake],
  [/^professional-services/, Handshake],
  [/^(project|work-management)/, ListChecks],
  [/^(telecom|connectivity)/, RadioTower],
  [/^(web3|blockchain|crypto)/, Boxes],
  [/^(wholesale|distribution)/, Warehouse],
  // Broad concept families (original rules).
  [/^(b2b|saas|software)/, Cloud],
  [/^(fintech|banking|finance|payments|wealth)/, Wallet],
  [/^(health|medical|wellness|mental)/, Heart],
  [/^(marketing|sales|content|crm|growth|ads|advertising)/, Megaphone],
  [/^(industry|infrastructure|manufacturing|logistics|construction|energy)/, Factory],
  [/^(public|gov|legal)/, Landmark],
  [/^(consumer|lifestyle|commerce|d2c|retail)/, ShoppingBag],
  [/^(edtech|education|learning|tutor)/, GraduationCap],
  [/(care|telehealth|clinic)/, Stethoscope],
  [/^(hr|recruit|talent|career|jobs)/, Briefcase],
  [/^(ai|ml|machine-learning|llm|agents)/, Cpu],
  [/^(creative|design|art|media)/, Sparkles],
  [/^(devtools|developer|coding|api|cli)/, Code],
  [/^(travel|hospitality|tourism)/, Plane],
  [/^(food|restaurant|dining|kitchen)/, UtensilsCrossed],
  [/^(real-estate|proptech|housing|home)/, Home],
  [/^(supply|delivery|fleet|trucking)/, Truck],
  [/^(climate|sustain|green|cleantech)/, Leaf],
  [/^(music|audio|podcast|sound)/, Music],
];

export function categoryIcon(slug: string | null | undefined): ComponentType {
  if (!slug) return Layers;
  const s = slug.toLowerCase();
  for (const [re, icon] of SLUG_RULES) {
    if (re.test(s)) return icon;
  }
  return Layers;
}
