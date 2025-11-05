"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.addRandomOffset = addRandomOffset;
exports.getRandomElement = getRandomElement;
exports.getRandomElements = getRandomElements;
exports.generatePhoneNumber = generatePhoneNumber;
exports.getPostcodeData = getPostcodeData;
const postcodes_1 = require("../data/postcodes");
function addRandomOffset(coord) {
    return coord + (Math.random() - 0.5) * 0.02;
}
function getRandomElement(array) {
    return array[Math.floor(Math.random() * array.length)];
}
function getRandomElements(array, count) {
    const shuffled = [...array].sort(() => 0.5 - Math.random());
    return shuffled.slice(0, count);
}
function generatePhoneNumber() {
    return `07${Math.floor(Math.random() * 900000000 + 100000000)}`;
}
function getPostcodeData(postcode) {
    return postcodes_1.POSTCODES[postcode];
}
//# sourceMappingURL=helpers.js.map