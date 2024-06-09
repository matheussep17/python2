<html>
  <head>
    <style>
      .form-container {
        background-color: #ffffff;
        padding: 20px;
        border: 1px solid #cccccc;
        border-radius: 10px;
        box-shadow: 2px 2px 10px #cccccc;
      }

      .form-control {
        width: 100%;
        padding: 10px;
        margin-bottom: 20px;
        border: 1px solid #cccccc;
        border-radius: 5px;
      }

      .form-label {
        font-weight: bold;
        margin-bottom: 10px;
      }

      .table-container {
        overflow-x: auto;
        margin-top: 20px;
      }

      table {
        border-collapse: collapse;
        width: 100%;
      }

      th, td {
        border: 1px solid #cccccc;
        padding: 10px;
        text-align: left;
      }

      th {
        background-color: #0072c6;
        color: #ffffff;
        font-weight: bold;
      }

      tr:nth-child(even) {
        background-color: #f2f2f2;
      }
    </style>
  </head>
  <body>
    <div class="form-container">
      <form id="form">
        <div class="form-label">Nome:</div>
        <input type="text" class="form-control" id="nome" required>

        <div class="form-label">CPF:</div>
        <input type="text" class="form-control" id="cpf" required>

        <div class="form-label">Telefone:</div>
        <input type="text" class="form-control" id="telefone" required>

        <div class="form-label">Endereço:</div>
        <input type="text" class="form-control" id="endereco" required>

        <button type="submit" class="form-control">Cadastrar</button>
      </form>
    </div>

    <div class="table-container">
      <table id="table">
        <thead>
          <tr>
            <th>Nome</th>
            <th>CPF</th>
            <th>Telefone</th>
            <th>Endereço</th>
          </tr>
        </thead>
        <tbody id="table-body">
        </tbody>
      </table>
    </div>

    <script>
      const form = document.getElementById("form");
      const tableBody = document.getElementById("table-body");

      form.addEventListener("submit", (event) => {
        event.preventDefault();
