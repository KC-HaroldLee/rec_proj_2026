import pymupdf

target_pdf_path = "data/docs/rec/REC_2022.pdf"

doc = pymupdf.open(target_pdf_path)

print(doc.page_count)      # 전체 페이지 수
print(doc.metadata)        # 메타데이터 (제목, 저자 등)
print(doc.is_encrypted)    # 암호화 여부

# 전체 텍스트 추출
for page_no, page in enumerate(doc[10:20]): 
    blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
    blocks.sort(key=lambda b: (round(b[1], 1), b[0]))  # y 먼저, 그다음 x
    print(f"================{page.number} START ================")
    for b in blocks:
        print(b[4])
    print(f"================{page.number} END ================")
    print()
    

    


# # 특정 페이지만
# page = doc[0]
# text = page.get_text()

# # 다양한 출력 형식
# text_dict = page.get_text("dict")   # 위치, 폰트 정보 포함
# text_words = page.get_text("words") # 단어 단위 리스트
# text_html = page.get_text("html")   # HTML 형식


# for page_index in range(len(doc)):
#     page = doc[page_index]
#     images = page.get_images(full=True)
#     for img_index, img in enumerate(images):
#         xref = img[0]
#         base_image = doc.extract_image(xref)
#         image_bytes = base_image["image"]
#         ext = base_image["ext"]
#         with open(f"image_{page_index}_{img_index}.{ext}", "wb") as f:
#             f.write(image_bytes)