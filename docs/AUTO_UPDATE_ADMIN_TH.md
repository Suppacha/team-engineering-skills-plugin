# คู่มือผู้ดูแล release และ team-managed auto-update

> **NOT ACTIVATED — ยังไม่เปิดใช้งาน:** repository ยังไม่มีหลักฐานว่าตั้ง protected environment, stable channel, release และ pilot ครบจริง เอกสารนี้เป็น runbook ไม่ใช่ใบรับรองการเปิดใช้ ให้คง ZIP เป็น fallback จนผ่านทั้ง Admin configuration และ [pilot สี่คู่](AUTO_UPDATE_PILOT_TH.md)

ขอบเขตที่ตั้งใจรับรองคือ **Codex Desktop Personal บน macOS/Windows** และ Claude Code รุ่น/ระบบปฏิบัติการที่ผ่าน pilot เท่านั้น company Workspace **PAUSED**; Codex CLI/IDE และ Claude/ChatGPT cloud ไม่ได้ถูกรับรองโดยอัตโนมัติ CLI เป็นกลไกภายในของ installer ไม่ใช่ work surface ที่รับรอง

## เปิด release channel ที่ GitHub

ใช้ workflow `Promote reviewed stable release` เพื่อเลื่อน full candidate SHA จาก `main` ไป `stable` หลัง CI และ approval เท่านั้น ห้าม direct/force push, owner PAT หรือให้ workflow จาก PR ถือ writer credential

สร้าง protected environment ชื่อ `team-plugin-stable` และเก็บค่าต่อไปนี้ **ใน environment นี้เท่านั้น**; ห้ามตั้ง fallback ที่ repository/organization level. GitHub Actions expression แยก provenance ของค่าชื่อเดียวกันไม่ได้ ดังนั้น Task 6 Admin ต้องตรวจ live settings และยืนยันว่าไม่มี repository/organization variable หรือ secret ชื่อซ้ำก่อน activation

| ชนิด | ชื่อ | ค่าที่ต้องมาจากสถานะจริง |
| --- | --- | --- |
| Secret | `RELEASE_WRITER_PRIVATE_KEY` | private key ของ dedicated GitHub App ที่จำกัดเฉพาะ repository นี้ |
| Variable | `RELEASE_WRITER_APP_ID` | numeric App ID จริง |
| Variable | `RELEASE_REVIEWER_ID` | numeric GitHub ID ของ reviewer ที่ policy อนุมัติ |
| Variable | `RELEASE_ADMIN_EVIDENCE` | JSON ที่ Admin ตรวจ human + live checks ตาม schema ด้านล่าง |

App ใน workflow ขอ Contents: write และ Actions: read เฉพาะ repository `Suppacha/team-engineering-skills-plugin` พร้อม Metadata: read ที่ GitHub App มีโดยปริยาย; ไม่ขอ Environments หรือ Administration. [Get rules for a branch](https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch) ใช้ Metadata: read ส่วน [Get an environment](https://docs.github.com/en/rest/deployments/environments#get-an-environment) และ [List deployment branch policies](https://docs.github.com/en/rest/deployments/branch-policies#list-deployment-branch-policies) ใช้ Actions: read. ตั้ง required reviewer และปิด environment Admin bypass. Ruleset ของ `stable` ต้องป้องกัน deletion, non-fast-forward และการเขียนที่ไม่ผ่าน dedicated writer. หากสิทธิ์/plan ทำไม่ได้ให้หยุด ไม่ลด gate

Environment ต้องอนุญาตเฉพาะ branch `main` ผ่าน custom deployment branch policy: `protected_branches: false`, `custom_branch_policies: true` และรายการ policy ต้องมีเพียงชื่อ `main` ที่ `type: branch` เท่านั้น ห้าม wildcard, tag, branch เพิ่มเติม หรือโหมดทุก protected branch. Collector ตรวจ API-visible settings นี้ทุก release รวมทุกหน้า โดยรับ protection rules อย่างละหนึ่ง `required_reviewers` และ `branch_policy` ไม่ขึ้นกับลำดับ; rule ที่ไม่รองรับ/ซ้ำ/ขาดจะถูกปฏิเสธ. ช่วง pilot ต้องตรวจว่า API ส่ง `type: branch` จริง: [official REST schema](https://github.com/github/rest-api-description/blob/main/descriptions/api.github.com/api.github.com.json) นิยาม `type` เป็น `branch` หรือ `tag` แต่ไม่ได้บังคับให้มี และตัวอย่างบางหน้าละไว้ หาก response ไม่มี `type` ระบบจะหยุดเพราะแยก branch กับ tag ไม่ได้ ห้ามถือว่าค่า missing หมายถึง branch หรือใช้ Admin attestation แทนการอ่าน setting นี้

นำ Environments: read ออกจาก workflow แล้ว เพราะเป็นสิทธิ์เกินกว่าที่ endpoint เหล่านี้ต้องใช้; Admin ไม่ต้องเพิ่มสิทธิ์นี้เพื่อแก้ปัญหาการอ่าน environment หรือ branch policy

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

## Bootstrap `stable` ครั้งแรกอย่างปลอดภัย

ทำตามลำดับนี้ ห้ามข้ามไป import source ที่ยังไม่มี:

1. ตั้ง protections และ Admin evidence จาก live settings ให้ครบ รวมการยืนยันว่าไม่มีค่าชื่อซ้ำระดับ repository/organization
2. เลือก reviewed main SHA แบบเต็มที่อยู่บน `main` และยืนยัน exact three-OS CI ของ SHA เดียวกันว่า Windows, macOS และ Ubuntu ผ่านครบ Candidate แรกต้องสืบสายจาก reviewed V2.1 baseline `6ca868dbccba7d2e2f15dfd5cc6ac105980a8b13` ซึ่ง runtime ใช้เป็น `INITIAL_BASELINE`; PR1 ของ V2.1 เดิมไม่ได้ merge เข้าเส้นประวัติ `main` 2.0 จึงต้องนำ baseline นี้กลับมาด้วย history-preserving merge และ **ห้าม squash/rebase จน SHA นี้หายจาก ancestry**. ตรวจแบบ read-only จาก trusted checkout โดยแทน candidate SHA เต็มจริง:

   ```sh
   git merge-base --is-ancestor 6ca868dbccba7d2e2f15dfd5cc6ac105980a8b13 "FULL_CANDIDATE_SHA"
   ```

   exit 0 จึงยืนยัน ancestry; คำสั่งนี้ไม่แก้ branch/ref และไม่รัน candidate. หาก history หายหรือ shallow checkout พิสูจน์ไม่ได้ ให้หยุด activation และกู้ history-preserving merge ก่อน หาก baseline ที่ runtime ผูกไว้ผิดจริง ต้องทำ reviewed baseline correction ใน code พร้อม tests/review แยกต่างหาก ไม่เปลี่ยน input, สร้าง ancestry ปลอม หรือห้ามลด gate เพื่อให้ promotion ผ่าน
3. รัน first approved promotion ผ่าน `Promote reviewed stable release`; ให้ workflow สร้าง `stable` จาก candidate SHA ที่ตรวจแล้ว **ห้ามสร้าง `stable` ว่างหรือชี้ SHA ที่ยังไม่ผ่าน gate ด้วยมือ**
4. ตรวจ `stable` ref และ release record ว่าชี้ candidate SHA เดียวกัน พร้อม CI/approval evidence ที่ตรวจย้อนกลับได้
5. เมื่อ bootstrap สำเร็จแล้วจึงอนุมัติ updater artifact/checksum สำหรับ isolated Personal pilot และ enable Claude stable source สำหรับ pilot ห้ามเปิด production scheduler อัตโนมัติ

หาก promotion แรกถูกปฏิเสธหรือ record ไม่ครบ ให้หยุดและแก้ gate/หลักฐาน ห้ามสร้าง branch ชั่วคราวเพื่อทำให้ provider import ผ่าน

## เปิด pilot Codex Desktop Personal

1. สร้าง updater ZIP ด้วย `python3 scripts/build-updater.py --output dist/team-updater-2.2.0.zip`; ตรวจ reproducibility, contents และ SHA-256 แล้วให้ Admin แจก ZIP ที่ review แล้วพร้อม checksum และ reviewed SHA ผ่านช่องทางแจกซอฟต์แวร์ที่ทีมอนุมัติแยกจาก GitHub protected release ห้ามแนบ ZIP/checksum หรือ asset เพิ่มใน release นั้น: publisher และ reader กำหนดให้มี **เพียง `release-record.json` หนึ่ง asset** เท่านั้น ไม่เปลี่ยน storage/access ของ protected release
2. ผู้ดูแล release ต้องยืนยันว่า `v2.2.0` ยังไม่เคยเผยแพร่ หากมีแล้วให้เพิ่ม version ห้าม overwrite. Candidate ต้องตรง protected `stable`, release record `promoted`, tag/SHA และ digest ทุกจุด
3. ให้ operator ที่อนุมัติใช้ [คู่มือติดตั้ง Personal](PERSONAL_AUTO_UPDATE_TH.md) บน isolated macOS/Windows ด้วยสิทธิ์ผู้ใช้ปกติ Initial install ผ่านก่อนเปิด scheduler
4. ตรวจ scheduler logon + 4 ชั่วโมง, sleep/offline/reconnect, `status`/`pause`/`resume`/`uninstall-updater`, previous package และ `repair-required`; แยก installed evidence จาก loaded evidenceในแชตใหม่
5. Windows ต้องใช้เครื่องจริงที่มี Codex Desktop และ NTFS. ผล Windows CI หรือ CLI ไม่แทน Desktop/native-client pilot

ตัวอัปเดตเป็น per-OS-user/per-machine ไม่ใช่ per-account isolation. ห้ามอ้างว่าเปลี่ยน Workspace แล้ว local plugin ถูกถอนหรือซ่อนอัตโนมัติ company Workspace ยังพักไว้; หาก managed policy ขัดกับ Personal pilot ให้หยุด ไม่ bypass

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

ลำดับสถานะคือ implementation-tested → protected release published → Pilot-verified รายคู่ → Team-enabled เฉพาะคู่ที่ผ่าน. ก่อนเปลี่ยนขั้นให้ตรวจ candidate SHA/CI/release record, protections, human + live checks ของ Admin, updater checksum และผล [pilot](AUTO_UPDATE_PILOT_TH.md). ต้องมี GitHub release Admin ดำเนินการ protection/writer/approval จริงและผู้ทดสอบ Windows Desktop จริง; Windows CI ที่ผ่านเป็น CI evidence ไม่ใช่ native client rollout evidence

แหล่งอ้างอิงทางการ: [OpenAI Workspace plugin management](https://learn.chatgpt.com/docs/enterprise/plugin-management) · [Claude Code marketplace sources](https://code.claude.com/docs/en/plugin-marketplaces) · [Claude Code auto-update](https://code.claude.com/docs/en/discover-plugins#configure-auto-updates) · [Claude Code plugin reference](https://code.claude.com/docs/en/plugins-reference)
