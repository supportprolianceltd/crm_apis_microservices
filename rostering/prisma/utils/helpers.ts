// prisma/utils/helpers.ts
import { POSTCODES } from '../data/postcodes';

export function addRandomOffset(coord: number): number {
  return coord + (Math.random() - 0.5) * 0.02;
}

export function getRandomElement<T>(array: T[]): T {
  return array[Math.floor(Math.random() * array.length)];
}

export function getRandomElements<T>(array: T[], count: number): T[] {
  const shuffled = [...array].sort(() => 0.5 - Math.random());
  return shuffled.slice(0, count);
}

export function generatePhoneNumber(): string {
  return `07${Math.floor(Math.random() * 900000000 + 100000000)}`;
}

export function getPostcodeData(postcode: keyof typeof POSTCODES) {
  return POSTCODES[postcode];
}