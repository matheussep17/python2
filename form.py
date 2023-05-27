<html>
  <head>
    <style>
      form {
        width: 500px;
        margin: auto;
        padding: 50px;
        text-align: center;
      }
      input[type="text"], input[type="email"], select {
        width: 100%;
        padding: 10px;
        margin-bottom: 20px;
        font-size: 18px;
        border-radius: 5px;
        border: 1px solid #ccc;
      }
      input[type="submit"] {
        width: 30%;
        padding: 10px;
        font-size: 18px;
        border-radius: 5px;
        border: none;
        background-color: #4CAF50;
        color: white;
        cursor: pointer;
      }
      input[type="submit"]:hover {
        background-color: #3e8e41;
      }
    </style>
  </head>
  <body>
    <form>
      <h2>Formulário de compras</h2>
      <input type="text" placeholder="Nome completo" required />
      <input type="email" placeholder="Email" required />
      <select>
        <option value="item1">Item 1</option>
        <option value="item2">Item 2</option>
        <option value="item3">Item 3</option>
      </select>
      <input type="submit" value="Comprar">
    </form>
  </body>
</html>
