# Auto-update สำหรับ Codex Desktop บัญชีส่วนตัว

สถานะ: ผู้ใช้อนุมัติแบบแล้ว — **NOT ACTIVATED / ยังไม่เปิดใช้งานจริง**; การอนุมัติแบบไม่แทน release approval หรือ pilot

## 1. ขอบเขตที่ผู้ใช้ยืนยัน

- Codex Desktop บัญชีส่วนตัวบน macOS และ Windows; ไม่รับรองการใช้งานผ่าน CLI หรือ IDE extension
- อนุญาตตัวอัปเดตของทีม ติดตั้งต่อเครื่อง/ผู้ใช้ OS หนึ่งครั้ง ตรวจเมื่อเข้าสู่ระบบและทุก 4 ชั่วโมง
- ใช้คำสั่งจัดการ plugin ของ Codex เป็นกลไกภายในได้ สมาชิกไม่ต้องเปิด CLI เพื่อทำงานหรือสั่ง update เอง
- Claude Code คง native marketplace auto-update ตามแบบเดิม ไม่ใช้ตัวอัปเดต Codex ไปแก้ Claude settings
- พักการพัฒนาและเปิดใช้ company Workspace; เก็บโค้ด/เอกสารเดิมไว้ ไม่ลบหรืออ้างว่ารับรองแล้ว
- แบบนี้แทนข้อห้าม local updater และขอบเขต company-only ของสเปกเดิมเฉพาะ Codex personal เส้นทางใหม่นี้เท่านั้น
- ไม่เปลี่ยน release approval gate, privacy policy หรือเพิ่ม telemetry

## 2. ทางเลือกและการตัดสินใจ

เลือกตัวอัปเดตระดับผู้ใช้ของทีมร่วมกับ protected `stable` เดิม เพราะยังไม่มีหลักฐานเพียงพอว่าบัญชีส่วนตัวรับ Git marketplace updates โดยอัตโนมัติ
การอัปเดตด้วยปุ่มหรือคำสั่งเองยังคงเป็นทางกู้ปัญหา แต่ไม่ตรงเป้าหมายติดตั้งครั้งเดียว
ไม่เลือกอ้าง daily Workspace sync สำหรับบัญชีส่วนตัว และไม่เปลี่ยนไปใช้ Workspace บริษัทที่ผู้ใช้พักไว้

นี่คือ **Team-managed auto-update ไม่ใช่ native Codex auto-update**. ต้องระบุเช่นนี้ในคู่มือและชุดแจก

## 3. โครงสร้างและขอบเขตสิทธิ์

แบ่งเป็น release reader/verifier, staged package store, Codex installer adapter, OS scheduler adapter และ status CLI
ใช้ Python standard library สำหรับตัวอัปเดต และ Git สำหรับรับ source ตาม commit ที่ตรวจแล้ว ไม่รัน scripts จาก source ที่เพิ่งดาวน์โหลด
ตัวติดตั้งตรวจ Python 3.11 ขึ้นไป, Git และ Codex executable รุ่นที่รองรับก่อนแก้เครื่อง; ถ้าขาดให้หยุดพร้อมคำแนะนำ ไม่ดาวน์โหลด runtime หรือยกระดับสิทธิ์เงียบ ๆ
เส้นทาง executable ต้อง resolve เป็น absolute path และบันทึกหลังตรวจแล้ว ไม่อาศัย current directory หรือ PATH ของ scheduler ที่เปลี่ยนไป

- macOS: LaunchAgent ของผู้ใช้เฉพาะตัวอัปเดตนี้; ไม่ใช้ LaunchDaemon/root
- Windows: Task Scheduler ของผู้ใช้ `InteractiveToken`/least privilege ไม่เก็บ password และไม่ขอ Run with highest privileges
- ไม่มีงานรันขณะ logout ที่ต้องเก็บ credentials; trigger logon และ interval 4 ชั่วโมงเมื่อ user session พร้อม
- เครื่องหลับ/ปิด/ไม่มีอินเทอร์เน็ตไม่รับประกันเวลา delivery; ตรวจอีกครั้งเมื่อ session/scheduler กลับมาทำงาน
- อนุญาตเพียงหนึ่ง instance ต่อ installation ผ่าน OS-released lock; task ที่ชนกันออกโดยไม่เขียน
- จำกัดไฟล์ที่เขียนไว้ใน state/package directory ของ updater และรายการ plugin ของทีมผ่าน Codex command เท่านั้น
- ไม่อ่าน prompts, เอกสารงาน หรือ credentials; ไม่แก้ `AGENTS.md`, `CLAUDE.md`, `.team-ai`, permission settings หรือ plugin ของผู้อื่น
- ไม่แก้ไฟล์ config/marketplace/cache ของ Codex ด้วยมือ ใช้ public client commands ที่ตรวจ capability แล้ว

ขอบเขต storage/scheduler เป็นผู้ใช้ OS ไม่ใช่การแยกบัญชี Codex: ห้ามอ้างว่าเปลี่ยน Workspace แล้ว local plugin หายหรือถูกปิดตามบัญชีโดยอัตโนมัติ. Pilot ใช้บัญชีส่วนตัวเท่านั้น; หาก client แสดง managed policy ที่ไม่อนุญาตให้ติดตั้ง ให้หยุด ไม่ bypass. ผู้ที่สลับไป Workspace บริษัทต้องตรวจนโยบายบริษัทแยก การรับรองเส้นทางบริษัทและ account isolation ยังพักไว้

## 4. เส้นทางติดตั้งครั้งแรก

1. แสดง source repository, ชื่อ plugin, ขอบเขตไฟล์ และ scheduler ที่จะเพิ่มให้สมาชิกทราบ
2. ตรวจ prerequisites และ inventory เฉพาะชื่อ marketplace/plugin ของทีม หากชื่อชนกับ ZIP/local/Git source เดิม ให้หยุดและแสดงขั้นตอน migration ไม่ uninstall หรือ overwrite อัตโนมัติ
3. ตรวจ published release ที่ตรงกับ `stable` ตามหัวข้อ 5; ห้าม fallback ไป feature branch/main เมื่อยังไม่มี stable
4. เตรียม verified snapshot ของ marketplace ใน directory ที่ updater เป็นเจ้าของ และ register เป็น local marketplace ผ่านคำสั่ง Codex ที่รองรับ
5. ติดตั้งเฉพาะ `team-engineering-skills@team-engineering-skills-marketplace` แล้วตรวจผลจริง
6. เมื่อ initial install ผ่านจึงเปิด scheduler; บันทึกสถานะ enabled และเวลาตรวจครั้งแรก
7. ให้สมาชิกเปิดแชตใหม่และตรวจ loaded evidence; initial install สำเร็จไม่เท่ากับ Desktop loading ผ่านแล้ว

เปลี่ยนเครื่องหรือต่างผู้ใช้ OS ต้องติดตั้งใหม่ ไม่มีคำกล่าวอ้างว่า account sync ตัว scheduler ไปทุกเครื่อง
ตัวติดตั้งต้อง idempotent: รันซ้ำกับ source ที่ตนเป็นเจ้าของไม่เพิ่ม scheduler/marketplace ซ้ำ

## 5. การเลือกรุ่นและตรวจความถูกต้อง

ต้นทางคงที่ `Suppacha/team-engineering-skills-plugin` และ branch `stable`. สมาชิกไม่ต้องมี GitHub token สำหรับ public release
อ่าน stable SHA เต็ม จากนั้นอ่าน VERSION และ published release `v<version>` ที่ผูก SHA เดียวกัน ตรวจว่าไม่ใช่ draft/prerelease และ publisher record อยู่สถานะ `promoted`
ตรวจ repository, candidate SHA, previous stable SHA เมื่อเกี่ยวข้อง, record schema, approval provenance และ tag ว่าตรงกัน; ห้ามเชื่อเพียงข้อความชื่อ release หรือ `latest`
ตรวจ release-record asset digest เทียบ canonical record ตามรูปแบบ publisher เดิม; ข้อมูลจาก GitHub ทั้งหมดถือเป็น untrusted input จนผ่าน validation

การเชื่อถือการอนุมัติอาศัย GitHub repository protections, dedicated writer และ HTTPS ไม่ใช่ลายเซ็นอิสระหรือ server-enforced WORM. ผู้ดูแล repository ที่ถูกยึดบัญชียังเป็นความเสี่ยง ต้องระบุ ไม่โฆษณาว่าป้องกันทุก supply-chain attack

รับ Git source ตาม immutable SHA ใน staging ที่แยกจาก installed source ด้วย fixed remote, sanitized Git environment/config และ subprocess argument arrays (ไม่ shell interpolation). ห้าม submodules, hooks, external filters หรือ candidate executables
ตรวจ HEAD ตรง SHA, ขนาด/จำนวนไฟล์จำกัด, path traversal, symlink/reparse point, Windows reserved/case-collision และ package allowlist ก่อนคัดลอก
ใช้ validator ที่ติดตั้งมากับ updater ไม่ import หรือรัน validator ของ candidate. ตรวจ manifest/registry/VERSION/hash/license ให้ครบ
ถ้ารุ่นต่ำลง หรือเลขรุ่นเท่าเดิมแต่ SHA/payload เปลี่ยน ให้หยุด; รุ่น/SHA เดิมเป็น no-op
อ่าน stable อีกครั้งก่อน activate; ถ้าเปลี่ยนระหว่างตรวจให้เลื่อนการติดตั้งไปรอบถัดไป ไม่ติดตั้ง source ที่ไม่ตรงหลักฐาน
ใช้ verified local snapshot ในการติดตั้งเพื่อหลีกเลี่ยง CLI fetch mutable stable ซ้ำหลัง validation

HTTP มี timeout, response-size cap, bounded pagination/retries และ fixed endpoint allowlist; rate limit/offline ให้ backoff ไม่วนยิง ไม่ทำให้สถานะ installed กลายเป็น latest

## 6. Activation และความล้มเหลว

เก็บ staging, current และ previous snapshot แยกกัน พร้อม journal ของ transaction. ไม่แตะ current ก่อน validation ผ่าน
สลับเฉพาะ updater-owned source directory ด้วย rename/journal และเรียกติดตั้งเฉพาะ plugin ทีมผ่าน Codex จากนั้นตรวจ installed manifest/hash/source กับ candidate
ไม่กล่าวอ้าง atomic transaction ครอบคลุม Codex cache. หาก rename ถูก Windows file lock ขัดขวาง ให้หยุดและเก็บรุ่นเดิม; หาก CLI สำเร็จบางส่วน/timeout ให้ read back ก่อนตัดสินใจ ไม่ retry mutation แบบเดาสถานะ
หลัง crash ให้ตรวจ journal และ source/installed state; เมื่อพิสูจน์ความสอดคล้องไม่ได้ ให้แสดง `repair-required` และหยุด auto-install จนผู้ใช้ดำเนินการกู้
เก็บ previous verified snapshot ไว้สำหรับกู้เครื่องนั้น ไม่ force push stable ย้อนกลับ. Recovery ของทีมเป็น forward release เลขรุ่นสูงขึ้นตาม gate เดิม
รุ่นใหม่บนดิสก์ยังไม่เท่ากับ loaded ในแชตเดิม; ไม่ปิดแอปหรือเปลี่ยน context กลางงาน สมาชิกต้องเปิดแชตใหม่
updater binary/scripts ไม่ self-update จาก payload ของ plugin. ถ้า protocol/runtime ต้องเปลี่ยน ให้แจ้งว่าต้องอัปเดตตัว updater แยก ไม่ฝืนข้าม compatibility gate

## 7. คำสั่งและสถานะสำหรับผู้ใช้

ชุดแจกมี installer สำหรับ macOS/Windows และ entry point: `status`, `check`, `pause`, `resume`, `uninstall-updater`
`check` ตรวจ/ติดตั้งตาม gate เดียวกับ scheduler ไม่ใช่ bypass. `status` อ่าน state ไม่อ้าง loaded version จากการคาดเดา
แสดง enabled/paused, installed version/SHA, last check/result, available verified version และ reload-required; unknown/error แยกจาก up-to-date
เก็บ log แบบหมุนเวียนในเครื่อง เฉพาะ timestamp, version, SHA, status/error code และ client/OS version ไม่อัปโหลด ไม่เก็บ paths ของงานหรือบัญชี/ชื่อสมาชิก
เก็บ log ไม่เกิน 5 ไฟล์ ไฟล์ละ 1 MiB เพื่อจำกัดดิสก์; นี่คือ local diagnostic rotation ไม่ใช่การกำหนด retention ของ metadata ส่วนกลาง
`pause` ปิดเฉพาะ scheduler ทีม; `resume` เปิดหลัง capability/source check ผ่าน
`uninstall-updater` ถอนเฉพาะ scheduler ทีมและปิด updater คง plugin, backups และ project files. การลบข้อมูลหรือถอน plugin เป็น action แยกที่ต้องยืนยันเป้าหมาย

## 8. Tests และเกณฑ์พร้อมแจก

Automated CI macOS/Windows/Ubuntu: valid/no-op/version downgrade, SHA/record/tag/digest mismatch, draft/prepared release, manifest/hash drift, unsupported client, offline/rate-limit, concurrency, interrupted transaction, path attacks, duplicate source, pause/resume/uninstall scope และ instruction-file byte equality
Windows ต้องทดสอบ scheduler argument quoting/path spaces และ file-lock recovery; macOS ต้องทดสอบ LaunchAgent serialization และ no-root scope. Mock tests ไม่แทน scheduler live run
Integration ต้องพิสูจน์บน isolated test profile ว่า Codex command ติดตั้ง snapshot version ใหม่ด้วยชื่อเดิมและตรวจผลกลับได้จริง ก่อนเปิด scheduler ใน profile ใช้งาน

Live pilot สี่คู่: Codex Desktop personal/macOS, Codex Desktop personal/Windows, Claude Code/macOS, Claude Code/Windows
แต่ละคู่ต้องมี A→B โดยผู้ใช้ไม่สั่ง update เอง, offline/reconnect, failed update, old session/new session, duplicate migration, recovery และไม่แก้ project instructions
สำหรับ Codex ต้องทดสอบ logon/4-hour scheduler จริง, pause/resume/uninstall จริง และแยก installed/loaded evidence; CLI success ไม่แทน Desktop success
ไม่มี Windows Desktop หรือบัญชี/เครื่องทดสอบ ให้รายงาน NOT RUN ไม่ใช้ Windows CI แทน. ไม่มีสิทธิ์ release ให้หยุดที่ release gate ไม่สร้างหลักฐานอนุมัติเอง

สถานะส่งมอบ: implementation-tested → protected release published → pilot-verified รายคู่ → team-enabled เฉพาะคู่ที่ผ่าน
ห้ามติดป้าย V2.2.0 เปิดใช้แล้วจาก ZIP/PR/CI อย่างเดียว. หาก V2.2.0 ถูกเผยแพร่ก่อนงานใหม่นี้ ต้องใช้เลขรุ่นใหม่ ไม่เขียนทับ release เดิม

## 9. ผลกระทบต่อเอกสารและงานเดิม

ปรับ Quick User Manual, Admin runbook, source evidence และ pilot matrix ให้ Codex personal เป็นเส้นทางหลัก ส่วน company Workspace ระบุ paused ไม่ใช่ blocked ที่สมาชิกต้องแก้
อธิบาย prerequisites, ติดตั้งต่อเครื่อง, initial install, scheduler, new chat, verify และการหยุดให้จบในคู่มือสั้น; แยกรายละเอียดกู้ระบบไว้ Appendix
ไม่เปลี่ยน skill payload ทั้ง 15 รายการโดยไม่จำเป็น; ถ้าเปลี่ยนต้องเพิ่ม version/hash ตาม policy
release workflow/protections เดิมยังต้องตั้งค่าจริงและผ่านการอนุมัติของผู้ดูแลก่อน publish; การอนุมัติสเปกนี้ไม่แทน GitHub release approval

## 10. หลักฐานและข้อจำกัดที่ตรวจแล้ว

- https://learn.chatgpt.com/docs/plugins ยืนยัน Personal marketplace และการเริ่มแชตใหม่หลังติดตั้ง แต่ไม่ได้ให้หลักประกัน Git auto-update ส่วนตัว
- Codex ที่เครื่องนี้: `codex-cli 0.155.0-alpha.2.6`; help มี `plugin marketplace add`, `upgrade`, `plugin add --json`, `plugin list --json`. Help ไม่พิสูจน์ Desktop compatibility หรือพฤติกรรมของ Windows
- ตัวอัปเดตใช้ client capability probe และ supported response schema ไม่รับรองทุกรุ่นจาก version string เพียงอย่างเดียว
- สเปกนี้ไม่แก้บัญชี ติดตั้ง scheduler เพิ่มสิทธิ์ GitHub หรือเปิด auto-update ใด ๆ
