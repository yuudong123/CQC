/* eslint-disable @typescript-eslint/no-require-imports -- 사진 내보내기 실행 도구 */
/* 동일 사과의 12장 프레임을 축소하여 웹 시연용으로 내보냅니다. */
const fs = require("node:fs/promises");
const path = require("node:path");
const sharp = require("sharp");
async function main() {
  const source = path.resolve(process.argv[2]);
  const index = JSON.parse(await fs.readFile(path.join(source, "index.json"), "utf8"));
  const groups = ["601143002000", "601033019000", "601031005000", "601142012000", "601032011000", "601141006000"];
  for (const [apple, group] of groups.entries()) {
    const item = index.find((row) => row.source_group_id === group && row.frame_count === 12 && row.default_playback);
    if (!item) throw new Error(`${group}: 완전한 12장 그룹이 없습니다.`);
    for (let frame = 0; frame < 12; frame++) {
      await sharp(path.join(source, item.path, `frame_${String(frame).padStart(2, "0")}.png`))
        .resize(480, 480, { fit: "inside" }).webp({ quality: 78 })
        .toFile(path.join(__dirname, "../public/apples", `apple-${apple}-${frame}.webp`));
    }
    console.log(`${apple}: ${item.inspection_id} · 12장`);
  }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
