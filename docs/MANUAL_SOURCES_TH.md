# หลักฐานและข้อจำกัด Quick User Manual

ตรวจวันที่ 17 กันยายน 2026 • เอกสารสำหรับผู้ดูแล ไม่ต้องอ่านเพื่อเริ่มใช้งาน

## ขอบเขตและหลักฐานภายใน

- ตรวจ repository ที่ commit `5fe5e20`: plugin VERSION และสอง manifests เป็น 2.1.0; registry มี 15 Skills แต่ละรายการเป็น 1.0.0
- ไม่แก้ Skill, registry, permission หรือพฤติกรรม runtime ในงานปรับคู่มือนี้
- ยังไม่ได้ทดสอบติดตั้ง/อัปเดตแบบ interactive ในทั้งสี่ Tool และไม่ได้พิสูจน์การอ่านจบภายในห้านาทีกับผู้ใช้จริง
- ไม่มีหลักฐานการ import ชุดทีมเข้า ChatGPT Workspace, ไม่มี Claude shared link และไม่มี ZIP ราย Skill สำหรับ Claude ใน deliverable นี้ จึงระบุเงื่อนไขก่อนทำขั้นตอนแทนการรับรองว่าเปิดใช้แล้ว
- คู่มือ Markdown แบ่ง Quick Start และสี่ Tool ให้ความยาวประมาณหนึ่งหน้าต่อส่วน; จำนวนหน้าพิมพ์ขึ้นกับฟอนต์/renderer ไม่ใช่ PDF ที่ล็อก pagination

## Evidence → Finding → Path

เปิดอ่านหน้าทางการจริง ไม่ใช้ search snippet เป็นหลักฐานสุดท้าย ตารางนี้อ้างอิงพฤติกรรมผู้ให้บริการ ไม่ใช่ผล pilot ของชุดทีม

| Evidence (ตรวจ 2026-09-17) | Finding | Path ในคู่มือ |
| --- | --- | --- |
| [OpenAI Plugins](https://learn.chatgpt.com/docs/plugins) | ต้องแยก client ที่รองรับ; ไม่มี Plugins ใน IDE extension; ติดตั้งแล้วเริ่มแชต/session ใหม่ | ChatGPT/Codex Install และ Use |
| [OpenAI packaging](https://developers.openai.com/plugins/build/plugins) | รองรับ local marketplace add และ marketplace upgrade; local source ต้องปรับไฟล์/รีสตาร์ตแอป | Codex Install/Update |
| [ChatGPT Skills](https://help.openai.com/en/articles/20001066) | สิทธิ์บัญชี/Workspace มีเงื่อนไข; shared install กับ uploaded copy คนละเส้นทาง | ChatGPT Install |
| [OpenAI workspace sync](https://learn.chatgpt.com/docs/enterprise/plugin-management) | ผู้ดูแล import/sync GitHub marketplace; pinned commit ไม่ตาม branch; sync ผิดพลาดอาจคงรุ่นเดิม | ChatGPT Update; อย่าเท่ากับ Git push แล้วผู้ใช้ได้ทันที |
| [Claude Skills](https://support.claude.com/en/articles/12512180-use-skills-in-claude) | ต้องเปิด code execution; shared skill ของผู้รับอัปเดตเมื่อใช้ครั้งต่อไป | Claude Install/Update |
| [Claude custom Skills](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills) | ต้องจัดแพ็กเกจและทดสอบ Skill สำหรับช่องทางนั้น | ไม่ใช้ marketplace ZIP ทั้งชุดแทน |
| [Claude Code discovery](https://code.claude.com/docs/en/discover-plugins) | user/project/local scopes ต่างกัน; third-party auto-update ไม่เปิดโดยปริยาย; reload จำเป็นเมื่อเปลี่ยนนอกเมนู | Claude Code Install/Update |
| [Claude Code reference](https://code.claude.com/docs/en/plugins-reference) | plugin list แสดง version/source/enabled; cache อิง plugin version | Claude Code Verify; การเผยแพร่ต้องเปลี่ยน version จริง |
| `plugins/team-engineering-skills/registry.json`, `VERSION`, `.codex-plugin/plugin.json`, `.claude-plugin/plugin.json` | framework version ไม่เท่ากับ skill version | คำถามตรวจหลักฐาน; ไม่ใช้รุ่นแอปแทน |

## อย่าปะปน version สามประเภท

ตัวอย่างสมมติเมื่อทีมประกาศ update: **ปลั๊กอิน 2.1.0 → 2.2.0** อาจรวม **test-case-design 1.0.0 → 1.1.0**; ไม่ได้แปลว่า Skill นั้นมี version 2.1/2.2 จริง และ 2.2.0 ยังไม่ใช่ release ที่ประกาศในงานนี้
`codex --version` / `claude --version` บอกรุ่น client อีกชุดหนึ่ง

ให้ผู้ดูแลประกาศ plugin version, commit/ref, skill versions ที่เปลี่ยน และช่องทางติดตั้งที่อนุมัติทุกครั้ง เวอร์ชันเท่ากันแต่อยู่คนละ commit อาจมีเนื้อหาต่างกัน โดยเฉพาะ pilot; ต้องเทียบหลักฐานเพิ่ม
คำถาม AI เป็นทางลัดเพื่อขอหลักฐาน ไม่ใช่ระบบตรวจรุ่นที่สร้างใหม่ ถ้าไม่แสดง path/manifest ของตัวที่โหลดจริง ห้ามผ่านเกณฑ์ Verify
`.team-ai/release.json` เป็น snapshot โปรเจกต์ ไม่ใช่หลักฐานของปลั๊กอินที่ client โหลด; update สองส่วนแยกกัน

## การตั้งค่าที่ผู้ดูแลต้องทำแยกจากสมาชิก

1. เตรียม client/บัญชีที่รองรับ และโปรเจกต์ตาม [ภาคผนวก Setup](MAINTAINER_APPENDIX_TH.md) ก่อนเริ่มจับเวลา 5 นาที
2. คู่มือใช้ clean replacement ของ extracted source ที่ path เดิมพร้อม backup ไม่ใช้การ add marketplace ชื่อซ้ำเพื่อเปลี่ยน source ต้อง pilot ขั้นตอนนี้กับ client รุ่นจริงก่อนแจก update; ห้ามลบ cache หรือ overwrite คำสั่งโปรเจกต์เพื่อแก้ปัญหา
3. ถ้าใช้ Git marketplace แทน ZIP: ผู้ใช้ที่ติดตั้งผ่าน marketplace ใช้คำสั่ง refresh ของ Tool ไม่ต้อง clone/pull อีกชุด; ผู้ที่ใช้ local Git checkout ต้อง pull/ref ตามที่ทีมอนุมัติก่อน refresh/reload เพราะ local directory ไม่ดึง remote ให้
4. Codex Git source ใช้ `codex plugin marketplace upgrade team-engineering-skills-marketplace` เพื่อ refresh catalog แล้วตรวจ installation ใน UI และเริ่ม session ใหม่; ไม่ถือว่าคำสั่งนี้พิสูจน์ installed/loaded version
5. Claude Code เพิ่ม plugin version เมื่อเผยแพร่จริง; commit ใหม่แต่ version เดิมอาจทำให้ update แจ้งว่าไม่มีรุ่นใหม่ ห้ามเรียกการเปลี่ยน source โดยคง 2.1.0 ว่า rollout รุ่นใหม่ที่ยืนยันแล้ว
6. ChatGPT: ขอสิทธิ์และเลือก ref สำหรับ workspace import; ตรวจ sync report สำเร็จ ไม่ถือว่ามี GitHub repo แล้วสมาชิกเห็น plugin
7. Claude: เตรียม ZIP ราย Skill พร้อม resource ที่ต้องใช้และหลักฐาน version หรือ shared skill ที่ควบคุมได้ ทดสอบความเข้ากันได้ อย่าประกาศว่ารองรับทุก Skill ใน cloud เพียงเพราะ upload ได้
8. Claude Code รุ่นใหม่บางแบบรองรับ sync จาก claude.ai แต่ไม่ใช่วิธีติดตั้ง local ในคู่มือนี้ อย่าให้ผู้ใช้ลงซ้ำทั้ง synced และ marketplace โดยไม่มีแผน

## Acceptance checklist

- [x] Quick Start มีตารางทั้งสี่ Tool ตามโจทย์
- [x] แต่ละ Tool มี Install / Use / Update Skill / Verify
- [x] แยก per-account, per-machine/user และ per-project
- [x] ไม่อ้าง auto-selection หรือ auto-update แบบรับประกันทุก client
- [x] แยกข้อมูล maintainer ออกจากคู่มือผู้ใช้
- [x] ใช้ลิงก์ทางการและบอกส่วนที่ยังตรวจไม่ได้
- [ ] Pilot ติดตั้ง/update/verify กับบัญชีจริงทั้งสี่ Tool และ macOS/Windows ที่เกี่ยวข้อง
- [ ] ให้สมาชิกใหม่ลอง Quick Start + Tool ของตน และจับเวลา/ถามห้าคำถามตามโจทย์

แบบบันทึกผล native client ที่ยังว่างอยู่: [Auto-update pilot — ทั้งสี่คู่เริ่ม NOT RUN](AUTO_UPDATE_PILOT_TH.md). ขั้นตอนตั้งค่าและย้าย source: [คู่มือ Admin](AUTO_UPDATE_ADMIN_TH.md).

ข้อจำกัด CLI: ใน environment ของรอบปรับเอกสารนี้ไม่พบ Codex executable ที่ path ที่ลอง จึงไม่อ้างว่ารันตัวอย่างติดตั้ง Codex สำเร็จ อ้างอิงคำสั่งจากเอกสารทางการเท่านั้น
