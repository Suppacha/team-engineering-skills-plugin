# คู่มือผู้ดูแล native auto-update

> **NOT ACTIVATED — ยังไม่เปิดใช้งาน:** repository ยังไม่มีหลักฐานว่าตั้ง protected environment, stable channel, Workspace import และ pilot ครบจริง เอกสารนี้เป็น runbook ไม่ใช่ใบรับรองการเปิดใช้ ให้คง ZIP เป็น fallback จนผ่านทั้ง Admin configuration และ [pilot สี่คู่](AUTO_UPDATE_PILOT_TH.md)

ขอบเขตที่ตั้งใจรับรองคือ Codex ใน **company Workspace** และ Claude Code รุ่น/ระบบปฏิบัติการที่ผ่าน pilot เท่านั้น บัญชีส่วนตัว, Codex CLI/IDE และ Claude/ChatGPT cloud ไม่ได้ถูกรับรองโดยอัตโนมัติ

## เปิด release channel ที่ GitHub

ใช้ workflow `Promote reviewed stable release` เพื่อเลื่อน full candidate SHA จาก `main` ไป `stable` หลัง CI และ approval เท่านั้น ห้าม direct/force push, owner PAT หรือให้ workflow จาก PR ถือ writer credential

สร้าง protected environment ชื่อ `team-plugin-stable` และเก็บค่าต่อไปนี้ **ใน environment นี้เท่านั้น**; ห้ามตั้ง fallback ที่ repository/organization level. GitHub Actions expression แยก provenance ของค่าชื่อเดียวกันไม่ได้ ดังนั้น Task 6 Admin ต้องตรวจ live settings และยืนยันว่าไม่มี repository/organization variable หรือ secret ชื่อซ้ำก่อน activation

| ชนิด | ชื่อ | ค่าที่ต้องมาจากสถานะจริง |
| --- | --- | --- |
| Secret | `RELEASE_WRITER_PRIVATE_KEY` | private key ของ dedicated GitHub App ที่จำกัดเฉพาะ repository นี้ |
| Variable | `RELEASE_WRITER_APP_ID` | numeric App ID จริง |
| Variable | `RELEASE_REVIEWER_ID` | numeric GitHub ID ของ reviewer ที่ policy อนุมัติ |
| Variable | `RELEASE_ADMIN_EVIDENCE` | JSON ที่ Admin ตรวจ human + live checks ตาม schema ด้านล่าง |

App ใช้ Contents: write, Actions: read และ Environments: read เฉพาะ repository `Suppacha/team-engineering-skills-plugin`; ไม่ให้ Administration:write. ตั้ง required reviewer และปิด environment Admin bypass. Ruleset ของ `stable` ต้องป้องกัน deletion, non-fast-forward และการเขียนที่ไม่ผ่าน dedicated writer. หากสิทธิ์/plan ทำไม่ได้ให้หยุด ไม่ลด gate

`RELEASE_ADMIN_EVIDENCE` ต้องตรงกับ runtime schema จริง:

```text
{
  "schema_version": 1,
  "repository": "Suppacha/team-engineering-skills-plugin",
  "environment_id": <LIVE_POSITIVE_INTEGER>,
  "reviewer_github_id": <LIVE_POSITIVE_INTEGER>,
  "writer_app_id": <LIVE_POSITIVE_INTEGER>,
  "ruleset_ids": [<LIVE_POSITIVE_INTEGER>, ...],
  "reviewed_at": "<LIVE_UTC_ISO_8601>",
  "evidence_reference": "<LIVE_NONEMPTY_REVIEW_REFERENCE>",
  "bypass_review": "only-dedicated-writer-app",
  "environment_admin_bypass": "disabled"
}
```

บล็อกนี้เป็น schema template ไม่ใช่ JSON ที่นำไปใช้ได้จนกว่าจะแทน placeholder ด้วยค่าจริง: ID และทุกสมาชิกของ `ruleset_ids` ต้องเป็น positive integer, `reviewed_at` ต้องเป็น UTC ISO 8601 ที่มี timezone และ `evidence_reference` ต้องเป็น string ไม่ว่าง **ห้ามสร้าง identity สมมติ**. Admin ต้องอ่าน environment ID, reviewer ID, writer App ID และ effective ruleset IDs จาก live settings แล้วเก็บ evidence reference ที่ตรวจย้อนกลับได้และไม่มี secret. ตรวจซ้ำและเปลี่ยน `reviewed_at` เมื่อ environment, reviewer, App permission, ruleset หรือ bypass เปลี่ยน ระบบตรวจ API-visible state ทุก release แต่ human evidence ยังจำเป็นสำหรับสิ่งที่ API มองไม่เห็น

## เปิด Codex company Workspace

1. ใน Admin > Plugins > Add > Import marketplace นำเข้า repository root `Suppacha/team-engineering-skills-plugin` โดยเลือก ref `stable` ไม่ใช่ `main` หรือ commit ที่หยุดนิ่ง
2. ตรวจ import/sync report และ plugin `team-engineering-skills`; แก้ error ก่อนกำหนด access ให้เฉพาะ role/group ที่อนุมัติ
3. ใช้บัญชีสมาชิกจริงติดตั้งจาก company Workspace แล้วเริ่ม session ใหม่ เก็บ installed evidence และ loaded evidence แยกกัน
4. การ sync ปกติเป็น **daily sync ไม่ใช่ immediate Push delivery**. Admin อาจใช้ Sync now เพื่อวินิจฉัย แต่ pilot auto-update ต้องมีรอบที่ไม่พึ่ง Sync now

Repository policy ไม่แทน Workspace access policy. บัญชีส่วนตัวที่มีอยู่เดิมอยู่นอก assurance และห้ามสรุปว่าการล็อกอินบัญชีเดียวทำให้ local installation ตามไปทุก client

## เปิด Claude Code stable marketplace

การเพิ่ม config อย่างเดียว **ไม่ได้ติดตั้ง plugin**. ไฟล์ [`config/claude-code-stable.example.json`](../config/claude-code-stable.example.json) เป็น merge-only fragment: merge เฉพาะ entry `team-engineering-skills-marketplace` เข้า settings ที่ policy อนุญาต ห้ามแทนที่ settings ทั้งไฟล์ และห้ามแก้ `permissions`, `env` หรือองค์กรเพื่อ bypass policy

เมื่อตรวจ trust/policy แล้ว ติดตั้งหนึ่งครั้งต่อเครื่องและผู้ใช้ OS:

```sh
claude plugin marketplace add Suppacha/team-engineering-skills-plugin@stable --scope user
claude plugin install team-engineering-skills@team-engineering-skills-marketplace --scope user
```

ตรวจ marketplace source/ref และ `claude plugin list --json`; จากนั้นเปิด Claude Code ใหม่ การตรวจอัปเดตเบื้องหลังตอน startup อาจถูกสุ่มหน่วงถึง 10 นาที เมื่อ installed version เปลี่ยนแล้วใช้ `/reload-plugins` หรือ session ใหม่เพื่อพิสูจน์ loaded version — `plugin list` อย่างเดียวไม่พิสูจน์ว่า session เก่าโหลดใหม่แล้ว

## ย้ายจาก ZIP หนึ่งครั้ง

ทำเฉพาะหลัง stable source พร้อมและขั้นตอนนี้ผ่าน pilot ของ client รุ่นนั้น:

1. บันทึก source/version ปัจจุบัน และเก็บ ZIP/local directory เป็น `backup`; ห้ามลบ cache, backup, project instructions, `AGENTS.md`, `CLAUDE.md` หรือ `.team-ai`.
2. ถ้ามี marketplace **ชื่อซ้ำ** ให้หยุดก่อน อย่า add ทับ source. ให้ผู้ใช้ยืนยันแล้วใช้คำสั่ง/เมนูที่ client รองรับเพื่อ disable หรือ uninstall รายการเดิม โดยไม่ลบ backup/project files
3. เพิ่ม stable marketplace และติดตั้ง plugin ตามช่องทางใหม่; initial install เป็นคนละขั้นกับ auto-update
4. เปิด session ใหม่ ตรวจ source/ref, installed version และ loaded version แล้วจึงเก็บ local ZIP ไว้เป็น fallback ที่ไม่ auto-update

การถอน stable source อาจกระทบ plugin ที่มาจาก marketplace นั้น โดยเฉพาะ Claude Code เมื่อเอา marketplace registration สุดท้ายออก จึงต้อง inventory ก่อนทุกครั้ง การ rollback ปกติให้เผยแพร่ payload ที่ทราบว่าดีด้วย version ที่สูงขึ้นผ่าน gate เดิม ไม่เลื่อน `stable` ย้อนหรือเขียนทับ version เดิม

## เกณฑ์เปิดให้ทีม

ลำดับสถานะคือ Repository-ready → Admin-configured → Pilot-verified → Team-enabled. ก่อนเปลี่ยนขั้นให้ตรวจหลักฐานจริง: candidate SHA/CI/release record, protections และ human + live checks ของ Admin, Workspace sync report, แล้วผล [pilot](AUTO_UPDATE_PILOT_TH.md). Windows CI junction ที่ผ่านเป็น CI evidence ไม่ใช่ native client rollout evidence

แหล่งอ้างอิงทางการ: [OpenAI Workspace plugin management](https://learn.chatgpt.com/docs/enterprise/plugin-management) · [Claude Code marketplace sources](https://code.claude.com/docs/en/plugin-marketplaces) · [Claude Code auto-update](https://code.claude.com/docs/en/discover-plugins#configure-auto-updates) · [Claude Code plugin reference](https://code.claude.com/docs/en/plugins-reference)
