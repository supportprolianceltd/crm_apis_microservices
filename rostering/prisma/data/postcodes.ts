// prisma/data/postcodes.ts
export const POSTCODES = {
  NW4: { lat: 51.5904, lon: -0.2393, area: 'Hendon' },
  HA2: { lat: 51.5589, lon: -0.3328, area: 'Harrow' },
  W5: { lat: 51.5131, lon: -0.3034, area: 'Ealing' },
  NW10: { lat: 51.5360, lon: -0.2466, area: 'Willesden' },
  N12: { lat: 51.6167, lon: -0.1658, area: 'North Finchley' },
  HA5: { lat: 51.6089, lon: -0.4183, area: 'Pinner' }
} as const;

export const SKILLS = [
  'Personal Care', 'Medication Administration', 'Mobility Support', 'Dementia Care',
  'Complex Care', 'Hoist Operation', 'PEG Feeding', 'Catheter Care', 'Stoma Care',
  'Diabetes Management', 'Companionship', 'Meal Preparation', 'Manual Handling'
];