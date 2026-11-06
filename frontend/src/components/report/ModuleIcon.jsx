import {
  Baby, Bank, Barbell, Buildings, Confetti, CrosshairSimple, Drop, FirstAid,
  ForkKnife, HardHat, Lightning, MapPin, Moon, PawPrint, Plant, ShieldCheck,
  ShoppingCart, SpeakerHigh, Student, Train, TrendUp, WifiHigh, Wind,
} from "@phosphor-icons/react";

export const MODULE_ICON = {
  air_quality: Wind,
  commute: Train,
  safety_day: ShieldCheck,
  safety_night: Moon,
  nightlife: Confetti,
  food: ForkKnife,
  schools: Student,
  parks: Plant,
  healthcare: FirstAid,
  daily_needs: ShoppingCart,
  fitness: Barbell,
  worship: Bank,
  water: Drop,
  power: Lightning,
  noise: SpeakerHigh,
  internet_wfh: WifiHigh,
  pet_friendly: PawPrint,
  cost: CrosshairSimple,
  infrastructure: HardHat,
  investment: TrendUp,
};

export const ModuleIcon = ({ module, ...props }) => {
  const Icon = MODULE_ICON[module] || Buildings;
  return <Icon weight="duotone" {...props} />;
};

export const OtherIcons = { Baby, MapPin };
