import subprocess
import os

def convert_to_videonote(input_path: str, output_path: str = "video_note.mp4", size: int = 360):
    """
    Конвертирует видео в квадрат 1:1, подходящий для отправки как video note.
    - input_path: путь к исходному видео
    - output_path: куда сохранить результат
    - size: размер по ширине/высоте (например, 360)
    """
    cmd = [
        "ffmpeg",
        "-y",  # автоматическая перезапись выходного файла, если он существует
        "-i", input_path,
        "-vf", f"scale={size}:{size}:force_original_aspect_ratio=decrease",
        "-c:v", "libx264",
        "-profile:v", "baseline",
        "-level", "3.0",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        output_path
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"Файл {output_path} успешно создан.")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при конвертации: {e}")

if __name__ == "__main__":
    # Пример использования:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(current_dir, "test_input.mp4")
    output_file = os.path.join(current_dir, "test_output.mp4")

    convert_to_videonote(input_file, output_file, size=360)
