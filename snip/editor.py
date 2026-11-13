"""Editor window: QGraphicsView/Scene with drawing tools, undo/redo, save, copy.

Public API: open_editor(pixmap) -> EditorWindow.  Run `python -m snip.editor`
for a standalone demo.
"""
import os
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (QAction, QActionGroup, QColor, QFont, QGuiApplication,
                           QImage, QKeySequence, QPainter, QPixmap, QUndoStack)
from PySide6.QtWidgets import (QColorDialog, QFileDialog, QFontComboBox, QGraphicsScene,
                               QGraphicsView, QMainWindow, QSpinBox, QToolBar, QToolButton,
                               QMessageBox)

from snip import settings
from snip.tools import TOOLS
from snip.tools.base import Options
from snip.tools.commands import CallbackCommand, RemoveItemsCommand
from snip.tools.text import TextItem

_windows = []  # keep references so windows are not garbage-collected
new_capture_hook = None  # set by the app: callable(editor) that starts a new capture


def open_editor(pixmap: QPixmap) -> "EditorWindow":
    win = EditorWindow(pixmap)
    _windows.append(win)
    win.show()
    win.raise_()
    win.activateWindow()
    return win


class CanvasView(QGraphicsView):
    """Forwards left-button mouse events to the active tool in scene coords."""

    def __init__(self, editor):
        super().__init__(editor.scene, editor)
        self.ed = editor
        self._active = False
        self._default = False
        self.setRenderHints(QPainter.RenderHint.Antialiasing
                            | QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor(45, 45, 48))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)

    def _pos(self, e) -> QPointF:
        return self.mapToScene(e.position().toPoint())

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(e)
            return
        tool, pos = self.ed.tool, self._pos(e)
        self._active = True
        self._default = tool.passthrough_at(pos)
        if self._default:
            super().mousePressEvent(e)
            if tool.passthrough:
                tool.press(pos)
        else:
            e.accept()
            tool.press(pos)

    def mouseMoveEvent(self, e):
        if not self._active:
            super().mouseMoveEvent(e)
            return
        tool = self.ed.tool
        if self._default:
            super().mouseMoveEvent(e)
        else:
            e.accept()
            tool.move(self._pos(e))

    def mouseReleaseEvent(self, e):
        if not self._active or e.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(e)
            return
        self._active = False
        tool = self.ed.tool
        if self._default:
            super().mouseReleaseEvent(e)
            if tool.passthrough:
                tool.release(self._pos(e))
        else:
            e.accept()
            tool.release(self._pos(e))

    def mouseDoubleClickEvent(self, e):
        if self.ed.tool.passthrough_at(self._pos(e)):
            super().mouseDoubleClickEvent(e)
        else:
            self.mousePressEvent(e)

    def keyPressEvent(self, e):
        f = self.scene().focusItem()
        editing = isinstance(f, TextItem) and f.editing
        if not editing and e.key() == Qt.Key.Key_Delete:
            self.ed.delete_selected()
            e.accept()
            return
        super().keyPressEvent(e)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            k = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.scale(k, k)
            e.accept()
        else:
            super().wheelEvent(e)


def _swatch(color: QColor):
    pm = QPixmap(16, 16)
    pm.fill(color)
    return pm


class EditorWindow(QMainWindow):
    def __init__(self, pixmap: QPixmap):
        super().__init__()
        self.setWindowTitle("Snip Editor")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.confirm_unsaved = True  # tests turn this off to close without a dialog
        self.options = Options()
        self.stack = QUndoStack(self)

        pm = QPixmap(pixmap)
        pm.setDevicePixelRatio(1.0)  # scene units == image pixels
        self.scene = QGraphicsScene(self)
        self.base = self.scene.addPixmap(pm)
        self.base.setZValue(-1000)
        self.scene.setSceneRect(0, 0, pm.width(), pm.height())

        self.view = CanvasView(self)
        self.setCentralWidget(self.view)
        self._fitted = False

        self.tools = {key: cls(self) for key, _label, cls in TOOLS}
        self.tool = self.tools["select"]
        self._build_actions()
        self._build_toolbars()
        self.set_tool("select")

        scr = QGuiApplication.primaryScreen()
        if scr is not None:
            g = scr.availableGeometry()
            w = min(pm.width() + 40, int(g.width() * 0.9))
            h = min(pm.height() + 140, int(g.height() * 0.9))
        else:
            w, h = pm.width() + 40, pm.height() + 140
        self.resize(max(w, 760), max(h, 300))

    # ---- UI ----
    def _act(self, text, slot, shortcut=None, checkable=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(shortcut)
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        self.addAction(a)
        return a

    def _build_actions(self):
        self.act_new = self._act("+ New", self.new_capture, QKeySequence.StandardKey.New)
        self.act_save = self._act("Save",self.save, QKeySequence.StandardKey.Save)
        self.act_copy_key = self._act("Copy (shortcut)", self._copy_shortcut,
                                      QKeySequence.StandardKey.Copy)
        self.act_copy = self._act("Copy", self.copy_to_clipboard)
        self.act_undo = self._act("Undo", self.undo, QKeySequence.StandardKey.Undo)
        self.act_redo = self._act("Redo", self.redo, QKeySequence("Ctrl+Y"))
        self.act_redo2 = self._act("Redo", self.redo, QKeySequence("Ctrl+Shift+Z"))
        self.act_delete = self._act("Delete", self.delete_selected)
        self.act_undo.setEnabled(False)
        self.act_redo.setEnabled(False)
        self.stack.canUndoChanged.connect(self.act_undo.setEnabled)
        self.stack.canRedoChanged.connect(self.act_redo.setEnabled)

    def _build_toolbars(self):
        tb = QToolBar("Tools", self)
        tb.setMovable(False)
        self.addToolBar(tb)
        tb.addAction(self.act_new)
        tb.addSeparator()
        group =QActionGroup(self)
        self._tool_actions = {}
        for key, label, _cls in TOOLS:
            a = QAction(label, self)
            a.setCheckable(True)
            a.triggered.connect(lambda _=False, k=key: self.set_tool(k))
            group.addAction(a)
            tb.addAction(a)
            self._tool_actions[key] = a
        tb.addSeparator()
        for a in (self.act_undo, self.act_redo, self.act_delete):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.act_save)
        tb.addAction(self.act_copy)

        self.addToolBarBreak()
        ob = QToolBar("Options", self)
        ob.setMovable(False)
        self.addToolBar(ob)
        o = self.options
        self.btn_color = QToolButton()
        self.btn_color.setText("Color")
        self.btn_color.setIcon(_swatch(o.color))
        self.btn_color.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_color.clicked.connect(self._pick_color)
        self.vis_color = ob.addWidget(self.btn_color)

        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 60)
        self.spin_size.setValue(o.size)
        self.spin_size.setPrefix("Width ")
        self.spin_size.valueChanged.connect(lambda v: setattr(self.options, "size", v))
        self.vis_width = ob.addWidget(self.spin_size)

        self.font_box = QFontComboBox()
        self.font_box.setCurrentFont(QFont(o.font_family))
        self.font_box.currentFontChanged.connect(self._font_changed)
        self.vis_text = [ob.addWidget(self.font_box)]
        self.spin_fsize = QSpinBox()
        self.spin_fsize.setRange(6, 300)
        self.spin_fsize.setValue(o.font_size)
        self.spin_fsize.setPrefix("Text ")
        self.spin_fsize.valueChanged.connect(self._fsize_changed)
        self.vis_text.append(ob.addWidget(self.spin_fsize))
        self.act_bold = QAction("B", self)
        self.act_bold.setCheckable(True)
        f = self.act_bold.font()
        f.setBold(True)
        self.act_bold.setFont(f)
        self.act_bold.toggled.connect(self._bold_changed)
        ob.addAction(self.act_bold)
        self.act_bg = QAction("Background", self)
        self.act_bg.setCheckable(True)
        self.act_bg.toggled.connect(self._bg_toggled)
        ob.addAction(self.act_bg)
        self.btn_bg = QToolButton()
        self.btn_bg.setIcon(_swatch(o.bg_color))
        self.btn_bg.setToolTip("Text background color")
        self.btn_bg.clicked.connect(self._pick_bg)
        self.vis_text += [self.act_bold, self.act_bg, ob.addWidget(self.btn_bg)]
        self.scene.selectionChanged.connect(self.update_option_visibility)
        self.update_option_visibility()

    # ---- tools ----
    def set_tool(self, key):
        self.scene.clearFocus()
        self.tool.deactivate()
        self.tool = self.tools[key]
        self._tool_actions[key].setChecked(True)
        self.view.viewport().setCursor(self.tool.cursor)
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag if key == "select"
                              else QGraphicsView.DragMode.NoDrag)
        if key not in ("select", "text"):
            self.scene.clearSelection()
        self.tool.activate()
        self.update_option_visibility()

    def update_option_visibility(self):
        """Show only the options relevant to the active tool / selected text."""
        t = self.tool
        text = t.shows_text or (t.name == "select" and bool(self._selected_text()))
        self.vis_color.setVisible(t.shows_stroke or text)
        self.vis_width.setVisible(t.shows_stroke)
        for a in self.vis_text:
            a.setVisible(text)

    # ---- options ----
    def _selected_text(self):
        return [i for i in self.scene.selectedItems() if isinstance(i, TextItem)]

    def _apply_style(self, **changes):
        """Apply style changes to selected text items as one undo step."""
        items = self._selected_text()
        cmds = []
        for it in items:
            old = it.style()
            new = dict(old, **changes)
            if new != old:
                cmds.append((it, old, new))
        if not cmds:
            return

        def setall(idx):
            for c in cmds:
                c[0].set_style(c[idx])

        self.stack.push(CallbackCommand("Text style", lambda: setall(2), lambda: setall(1)))

    def _pick_color(self):
        c = QColorDialog.getColor(self.options.color, self, "Color")
        if c.isValid():
            self.options.color = c
            self.btn_color.setIcon(_swatch(c))
            self._apply_style(color=QColor(c))

    def _pick_bg(self):
        c = QColorDialog.getColor(self.options.bg_color, self, "Text background")
        if c.isValid():
            self.options.bg_color = c
            self.btn_bg.setIcon(_swatch(c))
            self.act_bg.blockSignals(True)
            self.act_bg.setChecked(True)
            self.act_bg.blockSignals(False)
            self.options.bg_enabled = True
            self._apply_style(bg=QColor(c))

    def _bg_toggled(self, on):
        self.options.bg_enabled = on
        self._apply_style(bg=QColor(self.options.bg_color) if on else None)

    def _font_changed(self, font):
        self.options.font_family = font.family()
        self._apply_style(family=font.family())

    def _fsize_changed(self, v):
        self.options.font_size = v
        self._apply_style(size=v)

    def _bold_changed(self, on):
        self.options.bold = on
        self._apply_style(bold=on)

    # ---- actions ----
    def _editing_text(self):
        f = self.scene.focusItem()
        return f if isinstance(f, TextItem) and f.editing else None

    def undo(self):
        t = self._editing_text()
        if t is not None:
            t.document().undo()
        else:
            self.stack.undo()

    def redo(self):
        t = self._editing_text()
        if t is not None:
            t.document().redo()
        else:
            self.stack.redo()

    def delete_selected(self):
        if self._editing_text() is not None:
            return
        items = self.scene.selectedItems()
        if items:
            self.stack.push(RemoveItemsCommand(self.scene, items))

    def _copy_shortcut(self):
        if self._editing_text() is None and not self.scene.selectedItems():
            self.copy_to_clipboard()

    def render_image(self) -> QImage:
        """Render the scene at full image resolution (no selection/focus chrome)."""
        sel = self.scene.selectedItems()
        self.scene.clearSelection()
        self.scene.clearFocus()
        r = self.scene.sceneRect()
        img = QImage(int(r.width()), int(r.height()), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.white)
        p = QPainter(img)
        p.setRenderHints(QPainter.RenderHint.Antialiasing
                         | QPainter.RenderHint.SmoothPixmapTransform
                         | QPainter.RenderHint.TextAntialiasing)
        self.scene.render(p, QRectF(0, 0, img.width(), img.height()), r)
        p.end()
        for it in sel:
            it.setSelected(True)
        return img

    def copy_to_clipboard(self):
        QGuiApplication.clipboard().setImage(self.render_image())

    def new_capture(self):
        if new_capture_hook is not None:
            new_capture_hook(self)

    def save(self, path=None):
        if not path:
            name = datetime.now().strftime("snip-%Y%m%d-%H%M%S.png")
            start = os.path.join(settings.get_save_folder(), name)
            path, _ = QFileDialog.getSaveFileName(self, "Save image", start,
                                                  "PNG (*.png);;JPEG (*.jpg *.jpeg)")
            if not path:
                return False
        img = self.render_image()
        if path.lower().endswith((".jpg", ".jpeg")):
            img = img.convertToFormat(QImage.Format.Format_RGB32)
        ok = img.save(path)
        if not ok:
            QMessageBox.warning(self, "Save failed", f"Could not save {path}")
        else:
            self.stack.setClean()
        return ok

    # ---- window ----
    def showEvent(self, e):
        super().showEvent(e)
        if not self._fitted:
            self._fitted = True
            vp, r = self.view.viewport().size(), self.scene.sceneRect()
            if r.width() > vp.width() or r.height() > vp.height():
                self.view.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)

    def closeEvent(self, e):
        self.scene.clearFocus()
        if self.confirm_unsaved and not self.stack.isClean():  # unsaved edits: never lose them silently
            B = QMessageBox.StandardButton
            r = QMessageBox.question(self, "Unsaved changes", "Save changes before closing?",
                                     B.Save | B.Discard | B.Cancel, B.Save)
            if r == B.Cancel or (r == B.Save and not self.save()):
                e.ignore()
                return
        if self in _windows:
            _windows.remove(self)
        super().closeEvent(e)


def _demo_pixmap() -> QPixmap:
    pm = QPixmap(900, 560)
    pm.fill(QColor(235, 240, 250))
    p = QPainter(pm)
    p.setBrush(QColor(80, 140, 220))
    p.drawRect(60, 60, 300, 200)
    p.setBrush(QColor(240, 180, 60))
    p.drawEllipse(500, 120, 280, 280)
    p.drawText(80, 320, "Demo image: try pen, arrow, rectangle, text, crop")
    p.end()
    return pm


def main():
    app = QGuiApplication.instance()
    from PySide6.QtWidgets import QApplication
    if app is None:
        app = QApplication(sys.argv)
    open_editor(_demo_pixmap())
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
