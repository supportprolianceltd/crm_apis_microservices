import { POSTCODES } from '../data/postcodes';
export declare function addRandomOffset(coord: number): number;
export declare function getRandomElement<T>(array: T[]): T;
export declare function getRandomElements<T>(array: T[], count: number): T[];
export declare function generatePhoneNumber(): string;
export declare function getPostcodeData(postcode: keyof typeof POSTCODES): {
    readonly lat: 51.5904;
    readonly lon: -0.2393;
    readonly area: "Hendon";
} | {
    readonly lat: 51.5589;
    readonly lon: -0.3328;
    readonly area: "Harrow";
} | {
    readonly lat: 51.5131;
    readonly lon: -0.3034;
    readonly area: "Ealing";
} | {
    readonly lat: 51.536;
    readonly lon: -0.2466;
    readonly area: "Willesden";
} | {
    readonly lat: 51.6167;
    readonly lon: -0.1658;
    readonly area: "North Finchley";
} | {
    readonly lat: 51.6089;
    readonly lon: -0.4183;
    readonly area: "Pinner";
};
//# sourceMappingURL=helpers.d.ts.map