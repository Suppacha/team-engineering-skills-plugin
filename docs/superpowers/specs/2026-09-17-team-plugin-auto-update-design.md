# สเปก Auto-update — Team Engineering Skills

วันที่: 17 กันยายน 2026
สถานะ: ผู้ใช้อนุมัติสเปกในแชตแล้ว วันที่ 17 กันยายน 2026; การเปิดใช้งานจริงยังต้องผ่าน Admin configuration และ pilot
ฐานงาน: commit `6ca868d`, plugin 2.1.0, 15 Skills
ประเภทงาน: Architectural — เพิ่มกระบวนการเผยแพร่และเชื่อมระบบอัปเดตของผู้ให้บริการ

## ข้อตกลงเพิ่มเติมที่ผู้ใช้อนุมัติ 17 กันยายน 2026

ผู้ใช้ยอมรับให้ Admin ตรวจและบันทึกหลักฐานการตั้งค่าความปลอดภัยก่อนเปิดใช้ และตรวจซ้ำเมื่อเปลี่ยนสิทธิ์หรือกฎ ส่วนระบบยังตรวจ CI, SHA, เวอร์ชัน และผู้อนุมัติจริงทุก release. ผู้ใช้ขอ Push และเปิด Auto-update V2.2.0; คำขอนี้ไม่ใช่หลักฐานว่าตั้งค่า Admin หรือ pilot สำเร็จแล้ว.

- ตรวจ reviewer/environment และกฎที่ REST เปิดเผยทุก release; ข้อมูลที่อ่านไม่ได้ต้องรายงาน ไม่ตีความเป็นไม่มีข้อจำกัด.
- ส่วนที่ API ไม่รับรองการมองเห็น ได้แก่ bypass actors และ environment Admin bypass ให้ใช้บันทึกตรวจโดย Admin ผูก repository, environment ID, reviewer ID, writer App ID, ruleset IDs และเวลาตรวจ เก็บใน protected environment configuration ไม่รับ boolean จาก PR เป็นอำนาจ.
- บันทึกต้องมี evidence reference ที่ Admin ตรวจจริง; ค่าเริ่มต้นยังไม่ configured. เมื่อสิทธิ์หรือกฎเปลี่ยน Admin ต้องตรวจใหม่ก่อน release. นี่เป็นการรับรองแบบคนร่วมกับระบบ ไม่ใช่การตรวจ drift ทุกชนิดโดยอัตโนมัติ.
- ไม่ให้ writer Administration:write เพื่ออ่านหลักฐาน ไม่ใช้ owner PAT แทน dedicated App.
- ผูก candidate กับ trusted workflow run-name `Promote <full SHA>` ตรวจ display_title, repository/workflow/main และ run_attempt=1. Approval API ไม่มี candidate SHA หรือ timestamp ในแต่ละ review จึงห้ามสร้างข้อมูลเหล่านี้ขึ้นเอง; ใช้เวลาสังเกตหลักฐานแทนและระบุให้ชัด.
- Windows NTFS junction test ต้องรันจริงบน Windows CI; การข้ามบน macOS เป็นข้อจำกัดระบบปฏิบัติการ ไม่เปลี่ยนเป็นผลผ่านเทียม.

## 1. ผลลัพธ์ที่ต้องการและขอบเขต

สมาชิกตั้งค่าครั้งแรกแล้วไม่ต้องดาวน์โหลด ZIP, Git Pull หรือสั่ง update ทุกครั้งที่ทีมเผยแพร่รุ่นใหม่ ยอมรับการ Reload หรือเริ่ม session ใหม่เพื่อใช้รุ่นใหม่

- Codex: เฉพาะการใช้งานใน Workspace บริษัท บน client/version ที่ผ่าน pilot บน macOS และ Windows ไม่รับรองบัญชีส่วนตัวหรือ CLI ทุกแบบเพียงเพราะล็อกอินบัญชีเดียวกัน
- Claude Code: Git marketplace ของทีม ตั้งค่าต่อเครื่อง/ผู้ใช้ OS และเปิด auto-update ของ marketplace
- รับเฉพาะรุ่นที่ผ่าน CI และผู้มีอำนาจอนุมัติแล้ว ไม่มี auto-publish ทุก commit
- ใช้ repository เดิม `Suppacha/team-engineering-skills-plugin` ซึ่งเป็น public; ห้ามใส่ข้อมูลบริษัท credentials หรือรายชื่อสมาชิก
- ไม่สร้าง daemon, scheduled task, cron, launch agent, MCP service หรือ updater ใหม่บนเครื่องสมาชิก
- ไม่แก้ `AGENTS.md`, `CLAUDE.md`, `.team-ai` ของโปรเจกต์อัตโนมัติ การอัปเดต snapshot ยังต้อง review แยก
- ไม่เปิด telemetry หรือเปลี่ยนเงื่อนไข retention; หลักฐาน pilot เก็บโดยผู้ทดสอบ ไม่ส่งข้อมูลออกอัตโนมัติ

## 2. ทางเลือกและเหตุผล

เลือก **native provider update + protected Stable channel**: ดูแลระบบน้อย ใช้กลไกติดตั้งของ client และแยกการอนุมัติ release จากการรับ update
ไม่เลือก local ZIP เพราะยังต้องเปลี่ยนไฟล์เอง ไม่ตรงเป้าหมายติดตั้งครั้งแรกครั้งเดียว
ไม่เลือก custom updater เพราะเพิ่มโปรแกรม/สิทธิ์/ภาระความปลอดภัย และยังต้องแก้ปัญหา client cache/reload

## 3. สิ่งที่ repository มีอยู่และสิ่งที่ต้องเพิ่ม

ปัจจุบัน `verify.yml` มี CI สาม OS; `release.yml` เป็น manual ZIP artifact build เท่านั้น ไม่ใช่ release approval หรือ promotion gate
มีสอง marketplace manifests, registry/hash checks และ CODEOWNERS; CODEOWNERS ไม่ได้ตั้ง required review หรือป้องกัน branch เอง

ต้องเพิ่ม release eligibility/promotion workflow, regression tests ของ gate, release record, ตัวอย่างการตั้งค่า client และคู่มือ migration/rollback โดยคงชื่อ plugin และ marketplace เดิม
ไม่กำหนดเลข release ใหม่ว่าเผยแพร่แล้วในขั้นออกแบบ; implementation ต้องเพิ่ม SemVer จริงก่อน promotion ครั้งแรก

## 4. ช่องทางและหลักประกัน release

ใช้ branch `stable` เป็นช่องทางที่ผู้ให้บริการติดตาม ไม่ใช้ feature branch หรือ main โดยตรง ไม่ pin ผู้ใช้กับ commit ถ้าต้องการรับ update ในอนาคต
ลำดับงาน: พัฒนา → PR/review → commit ผู้สมัครบน main → CI สาม OS สำหรับ SHA นั้น → อนุมัติ release → promote SHA เดิมเข้า stable → provider sync → โหลดใน session ใหม่

### Gate ที่ต้องตรวจครบก่อนเลื่อน stable

1. รับ full commit SHA เท่านั้น ตรวจว่าอยู่ใน main ที่อนุมัติแล้ว ไม่ใช้ชื่อ branch แบบเปลี่ยนค่าได้ระหว่างรัน
2. CI ของ SHA นั้นผ่าน Windows/macOS/Ubuntu ครบ ไม่มี pending, cancelled, skipped job หรือ failed; ไม่ใช้ผลของ SHA อื่นหรือผล local แทน
3. ทั้ง manifests, registry และ VERSION ตรงกัน; version สูงกว่า stable ล่าสุด; payload/standards hashes และ license/package checks ผ่าน
4. หาก payload เปลี่ยน ต้องเพิ่ม version ของ Skill ที่เกี่ยวข้องและอัปเดต hash/provenance ตามกติกาเดิม
5. อนุมัติ release หลัง CI ผ่าน โดย repository owner (`Suppacha`) หรือผู้ที่ owner มอบหมายผ่านระบบสิทธิ์จริง การอนุมัติแบบระบบในแชตไม่ใช่การอนุมัติ release ใดโดยอัตโนมัติ
6. ตรวจ permission/approval enforcement ที่ GitHub จริงก่อนเปิดใช้งาน ใช้ protected release environment หรือกลไก approval ที่ตรวจตัวตนและผูก SHA ได้ ห้าม fallback เป็นข้อความ `approved: true` ที่ใครก็แก้ได้
7. serialise promotion, อ่าน stable SHA ใหม่ก่อนเขียน และปฏิเสธ stale/concurrent promotion; stable ต้อง fast-forward ไม่ force push
8. บัญชีทั่วไปและ workflow จาก PR ไม่มีสิทธิ์เลื่อน stable; ให้สิทธิ์เขียนเฉพาะส่วน promotion หลังผ่าน gate ไม่มี token ในไฟล์

Stable ต้องป้องกัน direct push/deletion/force push ตาม ruleset ที่ทดสอบแล้ว ไม่เปิดกว้างให้ bot bypass โดยไร้ gate ถ้า GitHub plan/สิทธิ์ทำ enforcement ไม่ได้ ให้หยุด activation และรายงาน ไม่ลดเกณฑ์เงียบ ๆ
การตั้งค่า GitHub/Workspace ที่เพิ่มสิทธิ์ต้องให้ Admin ตรวจและอนุมัติแยก ไม่ถือว่าไฟล์ config ใน repo เปิดใช้งานจริงแล้ว

### Release record

เก็บ plugin version, candidate SHA, previous stable SHA, CI run URLs, approval evidence URL/identity และเวลาที่ promote ในหลักฐาน release ของ GitHub ผูก immutable SHA; ไม่ใส่ prompts, project paths หรือข้อมูลลูกค้า
record สร้างโดย promotion workflow ไม่สร้าง commit เปลี่ยน payload หลังการทดสอบ SHA ที่กำลังเผยแพร่ ตรวจว่าหลักฐานถูกบันทึกก่อนประกาศ release สำเร็จ; ถ้าการบันทึกล้มเหลวต้องแจ้งสถานะบางส่วนและให้ผู้ดูแลแก้ ไม่ retry promotion แบบไม่ตรวจ state

## 5. Codex — Workspace บริษัท

Admin import repository marketplace โดยตั้ง ref เป็น `stable` และกำหนดสิทธิ์การติดตั้ง/ใช้งานเฉพาะบทบาทที่อนุมัติ ตรวจ sync report และรายการ plugin ที่สมาชิกมองเห็น
สมาชิกเลือก Workspace บริษัท ติดตั้งรายการทีมหนึ่งครั้งเมื่อจำเป็น แล้วเปิด session ใหม่ ไม่ติดตั้ง local marketplace ชื่อเดียวกันซ้อนเพื่อแก้ปัญหา
ใช้ provider sync; ไม่รับประกันทันทีหลัง Push ตามเอกสาร marketplace ใหม่เปิด sync รายวัน และ Admin สั่ง Sync now ได้ การทดสอบ Auto-update ต้องมีรอบที่ไม่อาศัย Sync now ด้วย

ต้องตรวจด้วยบัญชีสมาชิกจริงว่า client นั้นโหลด plugin จาก Workspace ได้ ไม่สรุปจากหน้า Admin เพียงอย่างเดียว ถ้า client/plan ไม่รองรับ ให้รายงานคู่ที่ยังไม่รองรับและไม่ติดตั้ง updater ทดแทน
เปลี่ยนไปบัญชีส่วนตัวถือว่าออกนอกขอบเขตรับรอง ไม่พยายามคัดลอกนโยบาย/สิทธิ์บริษัทตามไป
แหล่งอ้างอิง: [OpenAI Workspace plugin management](https://learn.chatgpt.com/docs/enterprise/plugin-management)

## 6. Claude Code — Git marketplace

ใช้ Git source ที่เลือก branch `stable` ผ่านรูปแบบที่เอกสาร client รองรับ คง local relative plugin source ภายใน marketplace; ไม่ใช้ ZIP หรือ local checkout เป็นช่องทาง auto-update
ตั้งค่าครั้งแรกต่อเครื่อง/ผู้ใช้: trust แหล่งทีม → add marketplace → install plugin → เปิด marketplace auto-update ผ่าน UI หรือ managed settings ที่ Admin อนุมัติ
ตัวอย่าง configuration ต้อง merge เฉพาะ entry ของทีม ไม่ overwrite settings ทั้งไฟล์ ไม่เปลี่ยน permission tools และไม่เปลี่ยนตัวแปร disable-update ระดับองค์กรเพื่อ bypass policy
third-party auto-update ปิดโดยปริยาย จึงต้องตรวจว่าค่านี้เปิดจริง ระบบทำงานหลังเริ่ม client และการโหลดรุ่นใหม่อาจต้อง `/reload-plugins` หรือ session ใหม่
เพิ่ม plugin version ทุก release; Git commit ใหม่อย่างเดียวไม่พอสำหรับแพ็กเกจที่ประกาศ version ไว้
แหล่งอ้างอิง: [Auto-update](https://code.claude.com/docs/en/discover-plugins#configure-auto-updates), [Version management](https://code.claude.com/docs/en/plugins-reference#version-management), [Marketplace sources](https://code.claude.com/docs/en/plugin-marketplaces)

## 7. เปลี่ยนจากการติดตั้งเดิม

สมาชิกที่ลง local ZIP มาก่อนต้องย้าย source **หนึ่งครั้ง**; ไม่อ้างว่า ZIP เดิมได้รับความสามารถ auto-update ย้อนหลังเอง
inventory source/version ก่อน → ตรวจแหล่งใหม่พร้อมใช้งาน → ปิด/ถอนรายการเก่าผ่าน client ตามการยืนยันของผู้ใช้ → ติดตั้งรายการที่ถูกต้อง → เปิด session ใหม่และตรวจ evidence
ไม่ลบ cache, ZIP backup, ไฟล์โปรเจกต์ หรือบัญชีเดิมอัตโนมัติ หากมี marketplace ชื่อซ้ำให้หยุดและใช้ขั้นตอน migration เฉพาะ client ที่ผ่าน pilot
เปลี่ยนเครื่อง: Codex ตรวจ Workspace installation ในบัญชีเดิม; Claude Code ต้องตั้งค่าเครื่องใหม่หรือรับ managed configuration แล้วตรวจจริงอีกครั้ง

## 8. ความผิดพลาดและ rollback

- CI ไม่ครบ/version ไม่เพิ่ม/approval ไม่ตรง SHA: ห้ามขยับ stable
- offline หรือ provider sync ล้มเหลว: แสดงสถานะว่าไม่ได้รุ่นใหม่ ตรวจว่ารุ่นเดิมยังใช้ได้ใน pilot; ไม่กล่าวอ้างว่า client ทุกตัวรับประกัน atomic update
- session เก่า: ไม่เขียนทับ context กลางงาน ให้แจ้งเปิด session ใหม่/reload
- อัปเดตมี regression: ระงับการ promote เพิ่มและแจ้งทีม ทางปกติให้คืน payload ที่ทราบว่าใช้งานได้ใน **version ใหม่ที่สูงขึ้น** ผ่าน CI/approval เดิม ไม่เลื่อน stable ย้อนกลับหรือเขียนทับ version เดิม
- กู้ฉุกเฉินรายเครื่องอาจต้องผู้ดูแลช่วยติดตั้งรุ่นที่อนุมัติและพัก auto-update ชั่วคราว ต้องระบุขั้นตอนเปิดกลับ ไม่รับประกัน rollback อัตโนมัติ

## 9. เกณฑ์ทดสอบและคำว่า “รับรอง”

### Automated

- gate ปฏิเสธ failed/missing/pending CI, SHA mismatch, commit นอก main, approval ที่ไม่มีสิทธิ์, version เดิม/ลดลง, inconsistent manifests, hash drift และ concurrent promotion
- gate ยอมรับเฉพาะ candidate ที่ครบเงื่อนไข; ทดสอบ first stable promotion แยกจาก upgrade
- workflow ฝั่ง PR ไม่มี publish credential; ตรวจ permission และ SHA binding หลัง approval ซ้ำ
- release record และคู่มือมี source/ref/version ที่ตรวจย้อนกลับได้; สคริปต์ไม่เขียนไฟล์คำสั่งโปรเจกต์

### Live pilot — ต้องครบสี่คู่

| Client | ระบบ | สิ่งที่ต้องพิสูจน์ |
| --- | --- | --- |
| Codex / Workspace บริษัท | macOS | ติดตั้ง A → รับ B ผ่าน sync → session ใหม่โหลด B |
| Codex / Workspace บริษัท | Windows | เหมือน macOS โดยบันทึก client version จริง |
| Claude Code / Stable Git marketplace | macOS | เปิด auto-update → รับ B โดยไม่สั่ง update → reload โหลด B |
| Claude Code / Stable Git marketplace | Windows | เหมือน macOS โดยไม่พึ่ง Bash script |

ใช้ข้อมูลสมมติและชุด A/B ที่เลขรุ่นต่างกัน ทดสอบในกลุ่ม pilot ที่อนุมัติก่อนเปิดให้ทีมทั้งหมด บันทึก framework/skill versions, source, released SHA, OS/client version, เวลารอ, วิธี reload และหลักฐาน installed กับ loaded แยกกัน
ต้องทดสอบ offline/failure, session เก่า, recovery แบบ forward release, บัญชี Codex ส่วนตัวไม่อยู่ในขอบเขต และไม่ทับ project instructions
คำตอบ AI ที่ไม่มี manifest/source evidence ไม่ผ่าน Verify หาก provider ไม่เปิดให้พิสูจน์ loaded version ต้องบันทึกข้อจำกัดและไม่ให้สถานะ “รับรอง”
repository CI ผ่าน, Admin sync ผ่าน, ติดตั้งได้ และ Auto-update ผ่าน เป็นคนละสถานะ ห้ามใช้แทนกัน

## 10. Deliverables และการเปิดใช้งาน

1. release gate/promotion workflow และ tests ใน repository พร้อม PR review
2. คู่มือ Admin สำหรับ stable protection, release approval, Workspace import และ Claude Code configuration
3. Quick User Manual เปลี่ยนเส้นทางหลักจาก ZIP เป็น Workspace/Git พร้อมขั้นตอนย้ายครั้งเดียว; ZIP คงเป็นทางเลือก offline ที่ไม่ auto-update
4. แบบบันทึก pilot/compatibility matrix และ release evidence ไม่เก็บข้อมูลจริงอัตโนมัติ
5. ขอบเขต rollout ที่ผ่านการทดสอบ พร้อมข้อจำกัดและ recovery runbook

แยก readiness เป็น Repository-ready → Admin-configured → Pilot-verified → Team-enabled
เอกสารสเปกนี้ไม่สร้าง stable branch, ไม่ปรับ ruleset/Workspace, ไม่เปิด auto-update และไม่เผยแพร่ release
ขั้นต่อไปหลังผู้ใช้ตรวจสเปก: สร้าง implementation plan ตาม writing-plans แล้วพัฒนา/ทดสอบเป็นส่วน ๆ
