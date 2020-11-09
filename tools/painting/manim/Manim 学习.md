# Manim 学习

毕竟磨刀不误砍柴工，Manim 所绘制的插图是除了 Tikz 之外最好看的，而且使用的是 Python 语言，很大程度上讲应该是之后主要使用的工具了。所以接下来的插图都用 Manim 来绘制！加油！

## [Manim tutorial 1：物体位置与坐标变换](https://www.bilibili.com/video/BV1p54y197cC)

* 二维坐标 `np.array([x, y, 0])`，三维坐标 `np.array([x, y, z])`

* 单位的长度由 `constants.py` 中的 `FRAME_HEIGHT` 和长宽比 `PIXEL_WIDTH/PIXEL_HEIGHT` 给出，其中画面高度 `FRAME_HEIGHT` 默认为 8 个单位。

* 画面中心为坐标原点 `ORIGIN=np.array([0, 0, 0])`。常见方向常量 `UP/RIGHT/LEFT/DOWN/UL/UR/DL/DR`。此外，还有 `TOP/LEFT_SIDE/RIGHT_SIDE/BOTTOM` 分别表示从画面中心指向画面上/左/右/下的向量。它们本质上都是 `np.array` 。

* 平移操作：`Mobject::shift(*vectors)`，将所有传入的 `vectors` 加起来进行相对移动

  >  注意：这里面的 `Mobject` 指 Manim 中的数学物品类，是屏幕上所有物品的超类，具体还可以细化成下面三种物品基类：
  >
  > 1. VMobject
  > 2. PMobject
  > 3. ImageMObject

* 移动到操作：`Mobject::move_to(point_or_mobject, aligned_edge=array([0,0,0]), coor_mask=array([1,1,1]))`

  移动到 `point_or_mobject` 的位置。

  `aligned_edge` 表示与目标位置对齐的方式：`LEFT` 和 `RIGHT` 分别表示左对齐和右对齐。这里的左对齐和右对齐分别指的是当前对象的 `get_left()/get_right()` 恰好等于目标位置。默认为中对齐，也即当前对象的 `get_center()` 恰好与目标位置重合。

* 缩放操作：`Mobject::scale(scale_factor, **kwargs)`，将当前对象缩放为原来的 `scale_factor` 倍。

  可以在 `**kwargs` 中传入参数 `about_point` 和 `about_edge`，前者表示缩放中心（默认为对象自身的中心），后者表示缩放时固定的边，比如传入 `about_edge=UP` 可以使得对象的上边缘位置不变只是长度发生变化。

* 旋转操作：`Mobject::rotate(angle, axis=array([0,0,1]), **kwargs)`，当前对象绕着轴 `axis` 旋转 `angle`，`angle` 的常见值是多少个角度，比如 `90 * DEGREES`；`axis` 的常见值是 `IN` 表示顺时针和 `OUT` 表示逆时针。

  可以在 `**kwargs` 中传入参数 `about_point` 作为旋转中心，默认为对象自身的中心。

* 翻转操作：`Mobject::flip(axis, **kwargs)`，当前对象沿着轴 `axis` 翻转 180 度。传入的 `axis` 是一个二维的轴的方向向量，比如 `UP`。

  可以在 `**kwargs` 中传入参数 `about_point` 作为轴上经过的一点，默认为 `ORIGIN` 过原点。

* 伸展操作：`Mobject::stretch(factor, dim, **kwargs)`，当前对象在维度 `dim` 上伸展 `factor` 倍，其中 `dim` 为 1/2/3 时分别表示 x/y/z 轴。

  可以在 `**kwargs` 中传入参数 `about_point` 表示伸展中心，默认为对象自身的中心。

* 移动到画面角落的操作：`Mobject::to_corner(corner, buff)`，当前对象和画面的角落 `corner` 对齐，比如左上角 `UL` 的话就是对象的左上角和画面的左上角重合，同理还有其他角落 `UR/DL/DR` 。`buff` 的默认值为 0.5。

* 移动到画面边缘的操作：`Mobject::to_edge(edge, buff)`，当前对象和画面的边缘 `edge` 对齐。和 `to_corner` 差不多。

* 对齐到点/对象的操作：`Mobject::align_to(mobject_or_point, direction)`，当前对象对齐到对象或点 `mobject_or_point`，传入的 `direction` 是一个向量 `L/R/U/D/UL/UR/DL/DR` 八个方向之一，如果传入的向量哪一维非 0，就会对当前对象进行对齐。比如 x 非 0 的话，就会让当前对象和目标的 `get_left()` 的对应维度坐标保持一致。

* 靠近操作：`Mobject::next_to(mobject_or_point, direction, buff, aligned_edge)`，表示让当前对象靠近对象或点 `mobject_or_point` 的 `direction` 方向（可选 U/D/L/R），距离 `buff` 可以自己调整，还可以通过 `aligned_edge` 微调 `direction` 垂直方向上的移动。

  > 高级操作：`next_to` 还支持让两个来自不同对象组 (VGroup) 的对象进行对齐。

* 宽度/高度设置操作：`Mobject::set_height/set_width`，加入 `stretch=True` 之后会固定另一边长度对于整体进行拉伸；否则效果等同于 `scale`。

## [Manim tutorial 2：常用几何类](https://www.bilibili.com/video/BV1kA411b7kq)

### Part1 线段/向量 Line/Arrow

* `Line()` 默认是从 (-1,0) 到 (1,0)，也可以传入两个端点 `Line(np.array([...]), np.array([...]))`。

  传入 `buff` 参数调整实际看到的线段与两个端点之间的距离，默认为 0。

  传入 `stroke_width` 调整线段的线宽。

  传入 `path_arc` 会将线段变成弧线，该参数即为圆心角。

  对于 `Line` 使用 `Mobject::scale` 只会调整长度而不会调整宽度。

  对于 `Line` 使用 `add_tip` 会在末尾加上箭头。

  `DashedLine` 继承自 `Line`，虚线；`Arrow` 也继承 `Line`，只不过末尾是箭头，且可以进行一些针对性的调整。`DoubleArrow` 则是开头和末尾都是箭头。

### Part2 弧线 Arc

暂时用不到。

### Part3 圆/椭圆 Circle/Dot/Ellipse

暂时用不到。

### Part4 圆环 Annulus/AnnulusScetor

暂时用不到。

### Part5 多边形 Polygon

* 创建多边形 `Polygen(p1, p2, p3)`。
* 多边形填充 `set_fill(color=ORANGE, opacity=0.8)`。
* 改变线宽和线的颜色 `set_stroke(color=ORANGE, width=2)`。
* 设置圆角半径获得圆角效果 `round_corners(0.2)`。
* 正多边形 `RegularPolygen(n)`，特例：三角形 `Triangle()`。

### Part6 矩形 Rectangle/Square/RoundedRectangle

* 矩形 `Rectangle` 参数：宽度 `width`，高度 `height`，颜色 `fill_color` 比如字符串 #66CCFF，透明度 `fill_opacity`。同样笔画相关的参数 `stroke_width/stroke_color/stroke_opacity`。

  渐变相关参数：渐变系数 `sheen_factor`，渐变方向 `sheen_direction` 比如 UR。

* 正方形 `Square` 参数：

  边长 `side_length` 默认为 2

* 圆角矩形 `RoundedRectangle` 继承 `Rectangle`，参数：

  圆角半径 `corner_radius`；

### Part7 对象组 VGroup

* 初始化 `b = VGroup(m1, m2)`，底层和 List 差不多
* 增加对象 `b.append(m3)`，类似于 push_back；另一个方向增加对象 `b.add_to_back(m3)`，类似于 push_front。
* 删除对象 `b.remove(m3)`。
* 通过下标进行访问 `b[0], b[1], b[2], b[3]`。
* 可以对对象组进行整体移动，比如 `b.shift` 进行整体平移；对于里面的某一个对象单独平移不会影响其他对象。
* 一个相对来说比较复杂的用法：`arrange`。
* VGroup 可以进行嵌套使用，因为它也是一个 VMobject。但是 `ImageMobject` 就不能放进去。

## [Manim tutorial 3：颜色的表示、运算和设置](https://www.bilibili.com/video/BV1vZ4y1x7hT)

### 颜色的表示

* `constants.py` 中定义的 54 种颜色常量可以直接使用，如 `BLUE/GREEN/YELLOW/GOLD/RED/PURPLE_E/D/C/B/A` 等。
* 用 16 进制表示颜色，如 #66CCFF，RGB 分别为 256 色；或者 `np.array([102, 204, 255])`；

## [Manim tutorial 4：插入图片与文字](https://www.bilibili.com/video/BV1CC4y1H7kp)

### 素材文件夹

推荐在 `manim.py` 和 `manimlib/` 目录的同级目录下新建 `assets` 目录，然后在里面建立三个子目录：

* raster_images
* svg_images
* sounds

然后在程序中就可以通过相对路径 `asserts/*` 来引用资源了。（其实这样做完之后在 manim 中直接使用不带拓展名的文件名即可）

### SVG/图片 SVGMobject/ImageMobject

### 文字类 TextMobject

`TextMobject` 是 `VMobject` 的子类，因此可以使用全部动画效果。

传入参数如下：一个扔到 $\LaTeX$ 里面编译的字符串，字符串开头需要加上 r 进行转义；颜色 `color`；背景笔画颜色 `background_stroke_color`；

在传入字符串的时候可以传入多个，它们分别编译并最后连在一起显示，每个都是一个子物体，可以通过下标进行访问。如果只传入一个，那么每个字符都是一个可以通过下标访问的子物体。于是每个字符都可以访问了。

### 公式类 TexMobject

写多行公式用的，目前用不到。

### 字体类 Text

只能传入一个字符串，可以自己定义字体，还有其他一些比较强大的功能。不过目前应该用不到。



