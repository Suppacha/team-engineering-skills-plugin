# ซ่อมไฟล์บันทึก V2.2.0 ที่ขาด (สำหรับผู้ดูแล)

เอกสารนี้ไม่ใช่คู่มือติดตั้งสำหรับสมาชิกทีม และไม่รับรองว่าเปิด Auto-update แล้ว

## เหตุการณ์และขอบเขต

การเผยแพร่ครั้งแรกสร้าง tag และ Draft Release ได้ แต่ยังไม่มี
`release-record.json` ชุดตรวจ run `35306681311` ยืนยันว่า metadata และ tag
ตรงกับ candidate และมี assets จำนวนศูนย์ โดยยังไม่ทราบข้อผิดพลาดต้นทาง
ของการอัปโหลดครั้งแรก เพราะ log เดิมไม่ได้เก็บ HTTP status ไว้

ชุดซ่อมผูกกับ repository `Suppacha/team-engineering-skills-plugin`,
tag `v2.2.0`, candidate `390c967b6daadaab0719a75a35147cb26ff5866f`
และ release ID `391171745` เท่านั้น ไม่มีช่องรับ target อื่น

## วิธีดำเนินการ

1. Merge ชุดซ่อมหลัง review และ CI ผ่าน Windows, macOS และ Ubuntu
2. เปิด Actions → **Repair v2.2.0 release record** → Run workflow บน `main`
3. เจ้าของบัญชีตรวจ run แล้วอนุมัติ environment `team-plugin-stable`
4. อ่านผลการซ่อมและผลตรวจกลับ ไม่ตีความเพียงการเริ่ม run ว่าสำเร็จ

ชุดซ่อมตรวจหลักฐานอนุมัติครั้งแรกแยกจากการอนุมัติใหม่ ใช้ App เดิม
ผ่าน secret ใน protected environment และทำงานเรียงกับงาน promote
ไม่ลดเงื่อนไขการอนุมัติของ workflow เผยแพร่ปกติ

หลังมีการ Re-run งานเดิม API ประวัติ review ที่ตรวจพบส่งรายการว่างกลับมา
จึงไม่อ้างว่าตรวจยืนยัน review เก่าจาก API ได้ ชุดซ่อมต้องตรวจ record ที่บันทึกไว้
ควบคู่กับ run attempt 1 และงาน preflight/publish จริงในช่วงเวลานั้น
กรณีนี้รายงาน `recorded-not-live` อย่างชัดเจน และยังต้องได้รับการอนุมัติซ่อมใหม่
จากผู้ตรวจที่กำหนด หากประวัติที่ API ส่งกลับขัดแย้งหรือกำกวม จะไม่เขียนข้อมูล

อนุญาตเฉพาะการเพิ่ม JSON ที่สร้างจาก record เดิมและตรวจ digest/ขนาด/state
หลังอัปโหลด ไม่ลบ ไม่แทนที่ asset ไม่เปลี่ยน body/tag/stable และไม่ publish
Draft Release หากพบข้อมูลขัดแย้งหรือผลไม่แน่นอน จะหยุดโดยไม่ retry คำสั่งเขียน
Log ต้องไม่แสดง token, private key, raw response หรือ exception ที่อาจมีข้อมูลลับ

## หลังซ่อม

การซ่อมสำเร็จหมายถึงไฟล์บันทึกครบเท่านั้น ไม่ใช่ release เผยแพร่สำเร็จ
การ promote ต้องเป็น dispatch ใหม่สำหรับ candidate เดิม ผ่านหลักฐานและ
การอนุมัติของ workflow ปกติอีกครั้ง ห้ามใช้ Re-run jobs เพื่อข้ามเงื่อนไข
first-attempt ห้ามย้าย tag หรือ force push

การรับรอง Auto-update บนเครื่องสมาชิกยังต้องแยกจากผล CI และผล release:
ต้องมีหลักฐานทดสอบจริงของ Codex Personal/Claude Code บน macOS/Windows
ตามคู่มือ pilot ก่อนอ้างว่าผ่านทุกเครื่อง

อ้างอิง API: [การอัปโหลด release asset](https://docs.github.com/en/rest/releases/assets#upload-a-release-asset)
และ [ประวัติ workflow run attempt](https://docs.github.com/en/rest/actions/workflow-runs#get-a-workflow-run-attempt)
