import streamlit as st
import PyPDF2
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import matplotlib.pyplot as plt
from pdf2image import convert_from_path
import numpy as np
import io
import tempfile
import os
import base64

st.set_page_config(page_title="PDF分割器", layout="wide")
st.title("PDF文档分割工具")

class PDFSplitter:
    def __init__(self):
        self.reader = None
        self.total_pages = 0
        self.splits_per_page = {}
        self.cut_points = []

    def load_pdf(self, uploaded_file):
        """加载PDF文件"""
        # 将上传的文件保存到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getbuffer())
            temp_path = tmp_file.name
        
        self.reader = PdfReader(temp_path)
        self.total_pages = len(self.reader.pages)
        self.splits_per_page = {i: 3 for i in range(self.total_pages)}
        self.temp_path = temp_path
        return self.total_pages

    def convert_page_to_image(self, page_num):
        """将PDF页面转换为图像"""
        if not (0 <= page_num < self.total_pages):
            raise ValueError(f"页码 {page_num + 1} 超出范围！PDF只有 {self.total_pages} 页")

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            writer = PdfWriter()
            writer.add_page(self.reader.pages[page_num])
            writer.write(temp_pdf)
            temp_pdf_path = temp_pdf.name

        images = convert_from_path(temp_pdf_path)
        os.unlink(temp_pdf_path)
        return images[0]

    def preview_cuts(self, page_num, cuts, direction='vertical'):
        """预览切割线位置"""
        try:
            image = self.convert_page_to_image(page_num - 1)
            width, height = image.size

            # 计算切割点
            num_cuts = self.splits_per_page[page_num - 1]
            if direction == 'vertical':
                self.cut_points = [int(width * cut / 100) for cut in cuts]
            else:
                self.cut_points = [int(height * cut / 100) for cut in cuts]

            fig, ax = plt.subplots(figsize=(10, 14))
            ax.imshow(image)

            # 绘制切割线
            for pos in self.cut_points[:-1]:
                if direction == 'vertical':
                    ax.axvline(x=pos, color='r', linestyle='--')
                else:
                    ax.axhline(y=pos, color='r', linestyle='--')

            ax.set_title(f'第 {page_num} 页预览 - {direction}方向切割 - {num_cuts}份')
            ax.axis('off')
            return fig

        except Exception as e:
            st.error(f"预览出错：{str(e)}")
            return None

    def split_and_save(self, page_settings):
        """根据设定的切割点分割并保存PDF"""
        try:
            writer = PdfWriter()

            for page_idx in range(self.total_pages):
                page = self.reader.pages[page_idx]
                original_width = float(page.mediabox.width)
                original_height = float(page.mediabox.height)

                settings = page_settings.get(page_idx, {
                    'direction': 'vertical',
                    'num_splits': 3,
                    'cuts': []
                })

                num_splits = settings['num_splits']
                direction = settings['direction']
                cuts = settings['cuts']

                if direction == 'vertical':
                    for i in range(num_splits):
                        temp_page = self.reader.pages[page_idx]
                        if cuts:
                            left = original_width * cuts[i] / 100
                            right = original_width * cuts[i + 1] / 100
                        else:
                            section_width = original_width / num_splits
                            left = i * section_width
                            right = (i + 1) * section_width
                        
                        temp_writer = PdfWriter()
                        temp_page = PdfReader(self.temp_path).pages[page_idx]
                        temp_page.mediabox.lower_left = (left, 0)
                        temp_page.mediabox.upper_right = (right, original_height)
                        temp_writer.add_page(temp_page)
                        writer.add_page(temp_page)
                else:
                    for i in range(num_splits):
                        temp_page = self.reader.pages[page_idx]
                        if cuts:
                            bottom = original_height * cuts[i] / 100
                            top = original_height * cuts[i + 1] / 100
                        else:
                            section_height = original_height / num_splits
                            bottom = i * section_height
                            top = (i + 1) * section_height
                        
                        temp_writer = PdfWriter()
                        temp_page = PdfReader(self.temp_path).pages[page_idx]
                        temp_page.mediabox.lower_left = (0, bottom)
                        temp_page.mediabox.upper_right = (original_width, top)
                        temp_writer.add_page(temp_page)
                        writer.add_page(temp_page)

            output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            writer.write(output_file)
            output_file.close()
            
            return output_file.name

        except Exception as e:
            st.error(f"保存出错：{str(e)}")
            return None

def get_binary_file_downloader_html(bin_file, file_label='File'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{file_label}">下载 {file_label}</a>'
    return href

# 创建Streamlit界面
def main():
    splitter = PDFSplitter()
    
    st.subheader("第一步：上传PDF文件")
    uploaded_file = st.file_uploader("选择PDF文件", type="pdf")
    
    if uploaded_file is not None:
        total_pages = splitter.load_pdf(uploaded_file)
        st.success(f"成功加载PDF文件：{uploaded_file.name}（共{total_pages}页）")
        
        st.subheader("第二步：设置分割参数")
        
        col1, col2 = st.columns(2)
        with col1:
            page_num = st.slider("选择页码", 1, total_pages, 1)
            direction = st.selectbox("切割方向", ["vertical", "horizontal"], 0)
        
        with col2:
            num_splits = st.slider("切割份数", 2, 6, 3)
            cuts_default = ",".join([str(i * (100/num_splits)) for i in range(1, num_splits)])
            cuts_input = st.text_input("切割点位置(%)", cuts_default, 
                                      help="输入切割点位置（百分比），用逗号分隔")
        
        # 解析切割点
        try:
            cut_values = [float(x.strip()) for x in cuts_input.split(',')]
            cut_values = [0] + cut_values + [100]
        except:
            st.error("切割点格式错误！请使用逗号分隔的数字")
            cut_values = None
        
        if cut_values:
            st.subheader("第三步：预览切割效果")
            preview_fig = splitter.preview_cuts(page_num, cut_values, direction)
            if preview_fig:
                st.pyplot(preview_fig)
            
            st.subheader("第四步：保存分割PDF")
            if st.button("生成分割PDF"):
                with st.spinner('处理中...'):
                    page_settings = {}
                    for p in range(splitter.total_pages):
                        page_settings[p] = {
                            'direction': direction,
                            'num_splits': num_splits,
                            'cuts': cut_values
                        }
                        
                    output_path = splitter.split_and_save(page_settings)
                    
                    if output_path:
                        st.success("PDF分割完成！")
                        st.markdown(get_binary_file_downloader_html(output_path, '分割后的PDF文件.pdf'), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
