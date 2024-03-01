import random
import asyncio
import aiohttp

from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Router, types, F


class OrderFood(StatesGroup):
    choosing_food_cat = State()
    choosing_food = State()


router = Router()


async def translate_text(text):
    from googletrans import Translator
    translator = Translator()
    text_trans = translator.translate(text, dest='ru')
    return text_trans.text


async def get_recipe(id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={id}") as response:
            data = await response.json()
            return data


@router.message(Command("category_search_random"))
async def keybord_cat(message: Message, command: CommandObject, state: FSMContext):
    if command.args is None:
        await message.answer("Ошибка: не переданы аргументы")
        return
    await state.update_data(chosen_food=int(command.args))
    async with aiohttp.ClientSession() as session:
        async with session.get("https://www.themealdb.com/api/json/v1/1/list.php?c=list") as response:
            cat = await response.json()
    categories = [meal["strCategory"] for meal in cat["meals"]]
    builder = ReplyKeyboardBuilder()
    for category_item in categories:
        builder.add(types.KeyboardButton(text=category_item))
        builder.adjust(4)
    await message.answer(
        "Для выбора категории блюда используйте клавиатуру: ",
        reply_markup=builder.as_markup(resize_keyboard=True),
    )
    await state.set_state(OrderFood.choosing_food_cat)


@router.message(OrderFood.choosing_food_cat)
async def food_chosen(message: types.Message, state: FSMContext):
    categ = message.text.lower()
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://www.themealdb.com/api/json/v1/1/filter.php?c={categ}") as response:
            data = await response.json()
    await message.answer("пожалуйста подождите перевод может занять время")
    food_info = [{"name": meal["strMeal"], "id": meal["idMeal"]} for meal in data["meals"]]
    amm = await state.get_data()
    selected_food_info = random.choices(food_info, k=amm['chosen_food'])
    food_ids = [food['id'] for food in selected_food_info]
    food_names = ", ".join(food['name'] for food in selected_food_info)
    await state.update_data(selected_food_ids=food_ids)
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Покажи рецепты"))
    translated_food_names = await translate_text(food_names)
    await message.answer(f"Могу предложить такие блюда: {translated_food_names}",
                         reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(OrderFood.choosing_food)


@router.message(OrderFood.choosing_food, F.text.in_("Покажи рецепты"))
async def show_recipes(message: Message, state: FSMContext):
    await message.answer("пожалуйста подождите перевод может занять время")
    food_ids_data = await state.get_data()
    selected_food_ids = food_ids_data.get("selected_food_ids", [])
    tasks = [get_recipe(id) for id in selected_food_ids]
    recipes_data = await asyncio.gather(*tasks)
    for data in recipes_data:
        food_name = data['meals'][0]['strMeal']
        recipe_instructions = data['meals'][0]['strInstructions']
        food_name_trans = await translate_text(food_name)
        recipe_instructions_trans = await translate_text(recipe_instructions)
        recipe_message = f"{food_name_trans} \nРецепт:\n{recipe_instructions_trans}"
        await message.answer(recipe_message)
    await message.answer("Приятного аппетита", reply_markup=types.ReplyKeyboardRemove())
    await state.clear()
