# เริ่มใช้ Team AI Operating Framework V2

Owner: Suppacha · Version: 2.0.0 · Repository นี้เป็น **public**:
[Suppacha/team-engineering-skills-plugin](https://github.com/Suppacha/team-engineering-skills-plugin)

ทีมใช้มาตรฐานและ 12 skills ชุดเดียวกัน แต่แต่ละคนเลือก Codex หรือ Claude Code
และใช้บัญชีที่องค์กรอนุมัติของตนเอง ไม่มีการแชร์บัญชีหรือเลือก/สลับผู้ให้บริการอัตโนมัติ
ระบบช่วยเลือก skill ตามงานใน client ที่เปิดอยู่ ไม่รับประกันว่า model จะเลือกถูกทุกครั้ง

## 1. ติดตั้ง plugin

Codex ที่รองรับ plugin CLI (ตรวจ `codex plugin --help` ก่อน):

```sh
codex plugin marketplace add Suppacha/team-engineering-skills-plugin --ref main
codex plugin add team-engineering-skills@team-engineering-skills-marketplace
```

เปิด task/session ใหม่หลังติดตั้ง หรือใช้ Plugins UI / `/plugins` ที่รองรับ
ไม่ใช่ทุกหน้าจอ ChatGPT จะรองรับวิธีนี้

Claude Code:

```sh
claude plugin marketplace add Suppacha/team-engineering-skills-plugin
claude plugin install team-engineering-skills@team-engineering-skills-marketplace
```

จากนั้นใช้ `/reload-plugins` ใน Claude Code
คำสั่ง GitHub ใช้ได้หลังเผยแพร่ source แล้ว; สำหรับ pilot ให้ใช้ path ของ ZIP ที่แตกแล้วแทนชื่อ repo
การใช้ `main` ติดตาม branch ได้ แต่ rollout ที่ต้องทำซ้ำควรใช้ release/ref ที่ owner ตรวจและอนุมัติแล้ว

## 2. เปิดใช้นโยบายใน project

ติดตั้ง plugin อย่างเดียวไม่ได้ทำให้ project อ่านนโยบายกลาง ต้อง bootstrap เพิ่ม
ใช้ Python 3.10+ และ release ที่ตรวจสอบแหล่งที่มาแล้ว โดย `/path/to/release`
คือโฟลเดอร์ marketplace ที่แตก ZIP แล้ว ไม่ใช่ไฟล์ ZIP หรือ path ของ plugin cache

```sh
python3 /path/to/release/plugins/team-engineering-skills/scripts/bootstrap-project.py \
  --release /path/to/release --project /path/to/existing-project --dry-run
python3 /path/to/release/plugins/team-engineering-skills/scripts/bootstrap-project.py \
  --release /path/to/release --project /path/to/existing-project
```

ผลลัพธ์ที่ต้อง review แล้ว commit ใน repo ของ project:

- `AGENTS.md`: มาตรฐานและ routing สำหรับ Codex
- `CLAUDE.md`: adapter `@AGENTS.md` ให้ Claude อ่านคำสั่งชุดเดียวกัน
- `.team-ai/`: สำเนานโยบาย, registry และ `release.json` พร้อม version/hash

คำสั่งนี้ไม่อ่าน source หรือ `.env` ของ project ไม่ติดต่อ network ไม่ตั้งค่า account
ไม่รัน scanner และไม่เก็บ telemetry หากมีชื่อไฟล์/โฟลเดอร์เป้าหมายอยู่แล้วจะหยุดโดยไม่เขียนทับ
กรณี project เดิม ให้สร้าง output ในโฟลเดอร์ทดลองว่าง แล้ว merge เองผ่าน PR
อย่าลบ instruction เดิมเพื่อให้คำสั่งผ่าน ไม่มี `--force`
หากเกิด I/O error อาจเหลือไฟล์ใหม่บางส่วน ให้ตรวจเองก่อนดำเนินการต่อ

## 3. Pilot ก่อน rollout

ใช้ข้อมูลสมมติและ prompt ใน [SMOKE_TESTS.md](SMOKE_TESTS.md) กับทั้งสอง client
ตรวจว่าอ่าน policy ได้, skill ที่เลือกตรงงาน, และแจ้งเมื่อ skill ไม่มี
บันทึก client/version, framework version, task category, skill, ผลทดสอบและข้อจำกัดด้วยตนเอง
ยังต้องทดสอบ interactive จริง; unit tests ไม่พิสูจน์ว่า model จะทำตาม instruction เสมอ

หากจะส่ง feedback ให้ใช้ [Issues](https://github.com/Suppacha/team-engineering-skills-plugin/issues)
และกรอกข้อมูลสังเคราะห์/ลบข้อมูลอ่อนไหวแล้วเท่านั้น ไม่มีระบบ upload อัตโนมัติ
ห้ามแนบ secret, private code, customer data, raw logs หรือ prompt จริงทั้งชุด

## 4. Update และ rollback

Codex:

```sh
codex plugin marketplace upgrade team-engineering-skills-marketplace
codex plugin add team-engineering-skills@team-engineering-skills-marketplace
```

Claude Code:

```sh
claude plugin marketplace update team-engineering-skills-marketplace
claude plugin update team-engineering-skills
```

เปิด session ใหม่/reload และ review policy snapshot แยกต่างหาก ไม่มี auto-migrate
rollback โดยกลับไปใช้ release ที่อนุมัติรุ่นก่อนและ revert commit ของ snapshot ผ่าน review
Uninstall plugin ไม่ลบ `AGENTS.md`, `CLAUDE.md` หรือ `.team-ai/`

## ขอบเขตที่ต้องเข้าใจ

AGENTS/CLAUDE/SKILL เป็นคำแนะนำ ไม่ใช่ security boundary
แม้ tool จะรันในเครื่อง แต่ cloud model calls อาจส่ง code ออกนอกเครื่องได้
ต้องตรวจ provider/account policy และ data classification ก่อนใช้ข้อมูลไม่สาธารณะ
CI ตรวจ tests, metadata และ hash ที่กำหนด ไม่ได้บังคับ AI policy ทุกข้อความ
CODEOWNERS ไม่ได้เปิด branch protection ให้เอง และยังไม่มีการตั้งค่า required reviews/rulesets จาก package นี้
workflow release ต้องสั่งเองและสร้าง ZIP artifact เท่านั้น ไม่ auto-publish ทุก commit

อ่านรายละเอียด [GOVERNANCE.md](GOVERNANCE.md).
อ้างอิงคำสั่ง: [OpenAI](https://developers.openai.com/plugins/build/plugins),
[Claude plugin](https://code.claude.com/docs/en/discover-plugins),
[Claude memory / AGENTS.md](https://code.claude.com/docs/en/memory#agentsmd).
