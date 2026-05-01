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

import type { ComponentType } from "svelte";

const SLUG_RULES: Array<[RegExp, ComponentType]> = [
  [/^(b2b|saas|software)/, Cloud],
  [/^(fintech|banking|finance|payments|wealth|insurance)/, Wallet],
  [/^(health|medical|wellness|mental)/, Heart],
  [/^(marketing|sales|content|crm|growth|ads|advertising)/, Megaphone],
  [/^(industry|infrastructure|manufacturing|logistics|construction|energy)/, Factory],
  [/^(public|gov|legal|nonprofit)/, Landmark],
  [/^(consumer|lifestyle|commerce|ecommerce|d2c|retail)/, ShoppingBag],
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
  [/^(climate|sustain|green|cleantech|agtech)/, Leaf],
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
